import os
import random
import numpy as np
import logging
import argparse

import cv2
import torch
import torch.backends.cudnn as cudnn
import torch.nn.parallel
import torch.optim
import torch.utils.data
import torch.multiprocessing as mp
import torch.distributed as dist
from os.path import join
from metrics import iou

from MinkowskiEngine import SparseTensor, CoordsManager
from util import config
from util.util import AverageMeter, intersectionAndUnionGPU, unpickle_data, pickle_data
from tqdm import tqdm
from tool.traincls import get_model

cv2.ocl.setUseOpenCL(False)
cv2.setNumThreads(0)


def worker_init_fn(worker_id):
    random.seed(1463 + worker_id)
    np.random.seed(1463 + worker_id)
    torch.manual_seed(1463 + worker_id)


def get_parser():
    parser = argparse.ArgumentParser(description='BPNet')
    parser.add_argument('--config', type=str, default='config/scannet/bpnet_5cm.yaml', help='config file')
    parser.add_argument('opts', help='see config/scannet/bpnet_5cm.yaml for all options', default=None,
                        nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.config is not None
    cfg = config.load_cfg_from_cfg_file(args.config)
    if args.opts is not None:
        cfg = config.merge_cfg_from_list(cfg, args.opts)
    return cfg


def get_logger():
    logger_name = "main-logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    fmt = "[%(asctime)s %(levelname)s %(filename)s line %(lineno)d %(process)d] %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    return logger


def main_process():
    return not args.multiprocessing_distributed or (
            args.multiprocessing_distributed and args.rank % args.ngpus_per_node == 0)


def main():
    args = get_parser()
    os.environ["CUDA_VISIBLE_DEVICES"] = ','.join(str(x) for x in args.train_gpu)
    cudnn.benchmark = True
    # for cudnn bug at https://github.com/pytorch/pytorch/issues/4107
    # https://github.com/Microsoft/human-pose-estimation.pytorch/issues/8
    # https://discuss.pytorch.org/t/training-performance-degrades-with-distributeddataparallel/47152/7
    # torch.backends.cudnn.enabled = False

    if args.manual_seed is not None:
        random.seed(args.manual_seed)
        np.random.seed(args.manual_seed)
        torch.manual_seed(args.manual_seed)
        torch.cuda.manual_seed(args.manual_seed)
        torch.cuda.manual_seed_all(args.manual_seed)
        # cudnn.benchmark = False
        # cudnn.deterministic = True

    print(
        'torch.__version__:%s\ntorch.version.cuda:%s\ntorch.backends.cudnn.version:%s\ntorch.backends.cudnn.enabled:%s' % (
            torch.__version__, torch.version.cuda, torch.backends.cudnn.version(), torch.backends.cudnn.enabled))

    if args.dist_url == "env://" and args.world_size == -1:
        args.world_size = int(os.environ["WORLD_SIZE"])
    args.distributed = args.world_size > 1 or args.multiprocessing_distributed
    args.ngpus_per_node = len(args.test_gpu)
    if len(args.test_gpu) == 1:
        args.sync_bn = False
        args.distributed = False
        args.multiprocessing_distributed = False
        args.use_apex = False

    # Following code is for caching dataset into memory
    if args.data_name == 'scannet_3d_mink':
        from dataset.scanNet3D import ScanNet3D, collation_fn_eval_all
        _ = ScanNet3D(dataPathPrefix=args.data_root, voxelSize=args.voxelSize, split='val', aug=False,
                      memCacheInit=True, eval_all=True, identifier=6797)
    elif args.data_name == 'scannet_cross':
        from dataset.scanNetCrossStyle import ScanNetCross, collation_fn, collation_fn_eval_all
        _ = ScanNetCross(dataPathPrefix=args.data_root, voxelSize=args.voxelSize, split='val', aug=False,
                         memCacheInit=True, eval_all=True, identifier=6797, val_benchmark=args.val_benchmark)

    if args.multiprocessing_distributed:
        args.world_size = args.ngpus_per_node * args.world_size
        mp.spawn(main_worker, nprocs=args.ngpus_per_node, args=(args.ngpus_per_node, args))
    else:
        main_worker(args.test_gpu, args.ngpus_per_node, args)


def main_worker(gpu, ngpus_per_node, argss):
    global args
    args = argss
    if args.distributed:
        if args.dist_url == "env://" and args.rank == -1:
            args.rank = int(os.environ["RANK"])
        if args.multiprocessing_distributed:
            args.rank = args.rank * ngpus_per_node + gpu
        dist.init_process_group(backend=args.dist_backend, init_method=args.dist_url, world_size=args.world_size,
                                rank=args.rank)

    model = get_model(args)
    if main_process():
        global logger
        logger = get_logger()
        logger.info(args)
        logger.info("=> creating model ...")
        logger.info("Classes: {}".format(args.classes))
        logger.info(model)

    if args.distributed:
        torch.cuda.set_device(gpu)
        args.test_batch_size = int(args.test_batch_size / ngpus_per_node)
        args.test_workers = int(args.test_workers / ngpus_per_node)
        model = torch.nn.parallel.DistributedDataParallel(model.cuda(), device_ids=[gpu])
    else:
        model = model.cuda()

    if os.path.isfile(args.model_path):
        if main_process():
            logger.info("=> loading checkpoint '{}'".format(args.model_path))
        checkpoint = torch.load(args.model_path, map_location=lambda storage, loc: storage.cuda())
        model.load_state_dict(checkpoint['state_dict'], strict=True)
        if main_process():
            logger.info("=> loaded checkpoint '{}' (epoch {})".format(args.model_path, checkpoint['epoch']))
    else:
        raise RuntimeError("=> no checkpoint found at '{}'".format(args.model_path))

    # ####################### Data Loader ####################### #
    if args.data_name == 'scannet_3d_mink':
        from dataset.scanNet3D import ScanNet3D, collation_fn_eval_all
        val_data = ScanNet3D(dataPathPrefix=args.data_root, voxelSize=args.voxelSize, split='val', aug=False,
                             memCacheInit=True, eval_all=True, identifier=6797)
        val_sampler = None
        val_loader = torch.utils.data.DataLoader(val_data, batch_size=args.test_batch_size,
                                                 shuffle=False, num_workers=args.test_workers, pin_memory=True,
                                                 drop_last=False, collate_fn=collation_fn_eval_all,
                                                 sampler=val_sampler)
    elif args.data_name == 'scannet_cross':
        from dataset.scanNetCrossStyle import ScanNetCross, collation_fn_eval_all
        val_data = ScanNetCross(dataPathPrefix=args.data_root, voxelSize=args.voxelSize, split='val', aug=False,
                                memCacheInit=True, eval_all=True, identifier=6797, val_benchmark=args.val_benchmark)
        val_sampler = None
        val_loader = torch.utils.data.DataLoader(val_data, batch_size=args.test_batch_size,
                                                 shuffle=False, num_workers=args.test_workers, pin_memory=True,
                                                 drop_last=False, collate_fn=collation_fn_eval_all,
                                                 sampler=val_sampler)
    else:
        raise Exception('Dataset not supported yet'.format(args.data_name))

    # ####################### Test ####################### #
    if args.data_name == 'scannet_3d_mink':
        validate(model, val_loader)
    elif args.data_name == 'scannet_cross':
        test_cross_3d(model, val_loader)


def validate(model, val_loader):
    torch.backends.cudnn.enabled = False  # for cudnn bug at https://github.com/pytorch/pytorch/issues/4107
    model.eval()
    with torch.no_grad():
        store = 0.0
        for rep_i in range(args.test_repeats):
            preds = []
            gts = []
            for i, (coords, feat, label, inds_reverse) in enumerate(tqdm(val_loader)):
                sinput = SparseTensor(feat.cuda(non_blocking=True), coords)
                predictions = model(sinput)
                predictions_enlarge = predictions[inds_reverse, :]
                if args.multiprocessing_distributed:
                    dist.all_reduce(predictions_enlarge)
                preds.append(predictions_enlarge.detach_().cpu())
                gts.append(label.cpu())
            gt = torch.cat(gts)
            pred = torch.cat(preds)
            current_iou = iou.evaluate(pred.max(1)[1].numpy(), gt.numpy())
            if rep_i == 0 and main_process():
                np.save(join(args.save_folder, 'gt.npy'), gt.numpy())
            store = pred + store
            accumu_iou = iou.evaluate(store.max(1)[1].numpy(), gt.numpy())
            if main_process():
                np.save(join(args.save_folder, 'pred.npy'), store.max(1)[1].numpy())


# def test_cross_3d(model, val_loader):
    # torch.backends.cudnn.enabled = False  # for cudnn bug at https://github.com/pytorch/pytorch/issues/4107
    # loss_meter, loss_meter_3d, loss_meter_2d, loss_meter_cls = AverageMeter(), AverageMeter(), AverageMeter(), AverageMeter()
    # intersection_meter_3d, intersection_meter_2d = AverageMeter(), AverageMeter()
    # union_meter_3d, union_meter_2d = AverageMeter(), AverageMeter()
    # target_meter_3d, target_meter_2d = AverageMeter(), AverageMeter()
    # loss_meter_mat = AverageMeter()
    # target_meter_mat, union_meter_mat, intersection_meter_mat = AverageMeter(), AverageMeter(), AverageMeter()
    # acc = 0
    # total = 0
    # model.eval()
    # with torch.no_grad():
    #     if main_process():
    #         pbar = tqdm(total=len(val_loader))
    #     gtseg3d = {}
    #     outseg3d = {}
    #     cc = {}
    #     outseg, outcls, outmat, gtcls, gtseg, gtmat = [], [], [], [], [], []
    #     for i, batch_data in enumerate(val_loader):
    #         if args.data_name == 'scannet_cross':
    #             if main_process():
    #                 pbar.update(1)
    #             (coords, feat, label_3d, color, label_2d, link, inds_reverse, cls, mat) = batch_data
    #             cc[i] = list(coords.cpu().numpy())
    #
    #             sinput = SparseTensor(feat.cuda(non_blocking=True), coords)
    #             color, link = color.cuda(non_blocking=True), link.cuda(non_blocking=True)
    #             label_3d, label_2d, = label_3d.cuda(non_blocking=True), label_2d.cuda(non_blocking=True)
    #             cls, mat = cls.cuda(non_blocking=True), mat.cuda(non_blocking=True)
    #             output_3d, output_2d, output_cls, output_mat = model(sinput, color, link)
    #             output_3d = output_3d[inds_reverse, :]
    #             output_2d = output_2d.contiguous()
    #             output_mat = output_mat.contiguous()
    #         else:
    #             raise NotImplemented
    #         if args.multiprocessing_distributed:
    #             dist.all_reduce(output_3d)
    #             dist.all_reduce(output_2d)
    #             dist.all_reduce(output_mat)
    #             print(output_3d.shape)
    #         # ############ 3D ############ #
    #
    #
    #         output_3d = output_3d.detach().max(1)[1]
    #         intersection, union, target = intersectionAndUnionGPU(output_3d, label_3d.detach(), args.classes,
    #                                                               args.ignore_label)
    #         if args.multiprocessing_distributed:
    #             dist.all_reduce(intersection), dist.all_reduce(union), dist.all_reduce(target)
    #         intersection, union, target = intersection.cpu().numpy(), union.cpu().numpy(), target.cpu().numpy()
    #         intersection_meter_3d.update(intersection)
    #         union_meter_3d.update(union)
    #         target_meter_3d.update(target)
    #         accuracy_3d = sum(intersection_meter_3d.val) / (sum(target_meter_3d.val) + 1e-10)
    #         # ############ 2D ############ #
    #         output_2d = output_2d.detach().max(1)[1]
    #         intersection, union, target = intersectionAndUnionGPU(output_2d, label_2d.detach(), args.classes,
    #                                                               args.ignore_label)
    #         if args.multiprocessing_distributed:
    #             dist.all_reduce(intersection), dist.all_reduce(union), dist.all_reduce(target)
    #         intersection, union, target = intersection.cpu().numpy(), union.cpu().numpy(), target.cpu().numpy()
    #         intersection_meter_2d.update(intersection)
    #         union_meter_2d.update(union)
    #         target_meter_2d.update(target)
    #         accuracy_2d = sum(intersection_meter_2d.val) / (sum(target_meter_2d.val) + 1e-10)
    #
    #         # ############ mat ############ #
    #         output_mat = output_mat.detach().max(1)[1]
    #         intersection, union, target = intersectionAndUnionGPU(output_mat, mat.detach(), args.classes,
    #                                                               args.ignore_label)
    #         if args.multiprocessing_distributed:
    #             dist.all_reduce(intersection), dist.all_reduce(union), dist.all_reduce(target)
    #         intersection, union, target = intersection.cpu().numpy(), union.cpu().numpy(), target.cpu().numpy()
    #         intersection_meter_mat.update(intersection)
    #         union_meter_mat.update(union)
    #         target_meter_mat.update(target)
    #         accuracy_mat = sum(intersection_meter_mat.val) / (sum(target_meter_mat.val) + 1e-10)
    #         print(output_mat.shape)
    #         print(accuracy_mat)
    #         # ############ cls ############ #
    #         output_cls = output_cls.detach().max(1)[1]
    #         correct_guessed = output_cls == cls
    #         cls_b_acc = torch.sum(correct_guessed.double()).item()
    #         acc += cls_b_acc
    #         total += output_cls.size(0)
    #         outseg.append(output_2d.detach_().cpu())
    #         outmat.append(output_mat.detach_().cpu())
    #         # outseg3d.append(output_3d.detach_().cpu().numpy())
    #         outcls.append(output_cls.detach_().cpu())
    #         gtcls.append(cls.cpu())
    #         gtseg.append(label_2d.cpu())
    #         # gtseg3d.append(label_3d.cpu().numpy())
    #         gtmat.append(mat.cpu())
    #         outseg3d[i] = output_3d.detach_().cpu().numpy()
    #         gtseg3d[i] = label_3d.cpu().numpy()
    #         if i > 7:
    #             break
    # if main_process():
    #     pbar.close()
    #
    # print("outcls.dsads")
    # outcls1 = torch.cat(outcls)
    # print("outseg.dsads")
    # outseg1 = torch.cat(outseg)
    # print("outmat.dsads")
    # # outseg3d1 = torch.cat(outseg3d)
    # outmat1 = torch.cat(outmat)
    # print("gtcls")
    # gtcls1 = torch.cat(gtcls)
    # print("gtmat")
    # gtmat1 = torch.cat(gtmat)
    # print("gtseg")
    # gtseg1 = torch.cat(gtseg)
    # # gtseg3d1 = torch.cat(gtseg3d)
    #
    # np.save(join(args.save_folder, 'outcls.npy'), outcls1.numpy()
    #         )
    #
    # print("outcls.dsads")
    # np.save(join(args.save_folder, 'outseg.npy'), outseg1.numpy()
    #         )
    # # np.save(join(args.save_folder, 'outseg3d.npy'), outseg3d1.numpy()
    # #         )
    # print("outseg.dsads")
    #
    # np.save(join(args.save_folder, 'outmat.npy'), outmat1.numpy()
    #         )
    #
    # print("outmat.dsads")
    #
    # # mIou_2d = iou.evaluate(store.max(1)[1].numpy(), gt.numpy())
    # np.save(join(args.save_folder, 'gtcls.npy'), gtcls1.numpy())
    # print("gtcls.dsads")
    #
    # np.save(join(args.save_folder, 'gtseg.npy'), gtseg1.numpy())
    # print("gtseg.dsads")
    #
    # # np.save(join(args.save_folder, 'gtseg3d.npy'), gtseg3d1.numpy())
    # np.save(join(args.save_folder, 'gtmat.npy'), gtmat1.numpy())
    #
    # print("gtmat.dsads")
    # pickle_data('outseg3d.pkl', outseg3d)
    #
    # print("outseg3d.dsads")
    # pickle_data('gtseg3d.pkl', gtseg3d)
    # print("chiago.dss")
    # import json
    # # with open('coords.json','w') as f:
    # #     json.dump(cc, f)
    # # pickle_data('coords.pkl', cc)
    #
    # iou_class_3d = intersection_meter_3d.sum / (union_meter_3d.sum + 1e-10)
    # accuracy_class_3d = intersection_meter_3d.sum / (target_meter_3d.sum + 1e-10)
    # mIoU_3d = np.mean(iou_class_3d)
    # mAcc_3d = np.mean(accuracy_class_3d)
    # allAcc_3d = sum(intersection_meter_3d.sum) / (sum(target_meter_3d.sum) + 1e-10)
    #
    # iou_class_2d = intersection_meter_2d.sum / (union_meter_2d.sum + 1e-10)
    # accuracy_class_2d = intersection_meter_2d.sum / (target_meter_2d.sum + 1e-10)
    # mIoU_2d = np.mean(iou_class_2d)
    # mAcc_2d = np.mean(accuracy_class_2d)
    # allAcc_2d = sum(intersection_meter_2d.sum) / (sum(target_meter_2d.sum) + 1e-10)
    # acc_cls = acc / total
    #
    # iou_class_mat = intersection_meter_mat.sum / (union_meter_mat.sum + 1e-10)
    # accuracy_class_mat = intersection_meter_mat.sum / (target_meter_mat.sum + 1e-10)
    # mIoU_mat = np.mean(iou_class_mat)
    # mAcc_mat = np.mean(accuracy_class_mat)
    # allAcc_mat = sum(intersection_meter_mat.sum) / (sum(target_meter_mat.sum) + 1e-10)
    #
    # if main_process():
    #     logger.info(
    #         'Val result: mIoU/mAcc/allAcc {:.4f}/{:.4f}/{:.4f}.'.format(mIoU_3d, mAcc_3d, allAcc_3d))
    #     logger.info(
    #         'Val result: mIoU/mAcc/allAcc {:.4f}/{:.4f}/{:.4f}.'.format(mIoU_2d, mAcc_2d, allAcc_2d))
    #     logger.info(
    #         'Val result: mIoU/mAcc/allAcc {:.4f}/{:.4f}/{:.4f}.'.format(mIoU_mat, mAcc_mat, allAcc_mat))
    #     logger.info('Class ACC{:.4f}'.format(acc_cls))


def test_cross_3d(model, val_data_loader):
    torch.backends.cudnn.enabled = False  # for cudnn bug at https://github.com/pytorch/pytorch/issues/4107
    intersection_meter = AverageMeter()
    union_meter = AverageMeter()
    target_meter = AverageMeter()
    with torch.no_grad():
        model.eval()
        store = 0.0
        for rep_i in range(args.test_repeats):
            preds, gts = [], []
            val_data_loader.dataset.offset = rep_i
            if main_process():
                pbar = tqdm(total=len(val_data_loader))
            for i, (coords, feat, label_3d, color, label_2d, link, inds_reverse) in enumerate(val_data_loader):
                if main_process():
                    pbar.update(1)
                sinput = SparseTensor(feat.cuda(non_blocking=True), coords)
                color, link = color.cuda(non_blocking=True), link.cuda(non_blocking=True)
                label_3d, label_2d = label_3d.cuda(non_blocking=True), label_2d.cuda(non_blocking=True)
                output_3d, output_2d = model(sinput, color, link)
                output_2d = output_2d.contiguous()
                output_3d = output_3d[inds_reverse, :]
                if args.multiprocessing_distributed:
                    dist.all_reduce(output_3d)
                    dist.all_reduce(output_2d)
                output_2d = output_2d.detach().max(1)[1]
                intersection, union, target = intersectionAndUnionGPU(output_2d, label_2d.detach(), args.classes,
                                                                      args.ignore_label)
                intersection, union, target = intersection.cpu().numpy(), union.cpu().numpy(), target.cpu().numpy()
                intersection_meter.update(intersection), union_meter.update(union), target_meter.update(target)

                preds.append(output_3d.detach_().cpu())
                gts.append(label_3d.cpu())
            if main_process():
                pbar.close()
            gt = torch.cat(gts)
            pred = torch.cat(preds)
            if rep_i == 0:
                np.save(join(args.save_folder, 'gt.npy'), gt.numpy())
            store = pred + store
            mIou_3d = iou.evaluate(store.max(1)[1].numpy(), gt.numpy())
            np.save(join(args.save_folder, 'pred.npy'), store.max(1)[1].numpy())

            iou_class = intersection_meter.sum / (union_meter.sum + 1e-10)
            # accuracy_class = intersection_meter.sum / (target_meter.sum + 1e-10)
            mIoU_2d = np.mean(iou_class)
            # mAcc = np.mean(accuracy_class)
            # allAcc = sum(intersection_meter.sum) / (sum(target_meter.sum) + 1e-10)
            if main_process():
                print("2D: ", mIoU_2d, ", 3D: ", mIou_3d)


if __name__ == '__main__':
    main()
