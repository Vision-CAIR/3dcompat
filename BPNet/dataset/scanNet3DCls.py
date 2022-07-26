#!/usr/bin/env python
"""
    File Name   :   CoSeg-scanNet3D
    date        :   14/10/2019
    Author      :   wenbo
    Email       :   huwenbodut@gmail.com
    Description :
                              _     _
                             ( |---/ )
                              ) . . (
________________________,--._(___Y___)_,--._______________________
                        `--'           `--'
"""
from dataset.utils import unpickle_data, pickle_data
import pandas as pd
import json
import torch.utils.data as data
import torch
import os
import os.path as osp
import trimesh
import numpy as np
from os.path import join, exists
from glob import glob
import multiprocessing as mp
import SharedArray as SA
import dataset.augmentation as t
from dataset.voxelizer import Voxelizer
from collections import defaultdict, Counter

N_POINTS_PER_PART = 5000

parts = ['arm', 'armrest', 'back', 'back_horizontal_bar', 'back_panel', 'back_vertical_bar', 'backrest', 'bag_body', 'base', 'base1', 'body', 'bottom_panel', 'bulb', 'bush', 'cabinet', 'caster', 'channel', 'container', 'containing_things', 'cushion', 'design', 'door', 'doorr', 'drawer', 'drawerr', 'foot_base', 'footrest', 'glass', 'handle', 'harp', 'head', 'headboard', 'headrest', 'keyboard_tray', 'knob', 'lamp_surrounding_frame', 'leg', 'legs', 'leveller', 'lever', 'lid', 'mattress', 'mechanism', 'neck', 'pillow', 'plug', 'pocket', 'pole', 'rod', 'seat', 'seat_cushion', 'shade_cloth', 'shelf', 'socket', 'stand', 'stretcher', 'support', 'supports', 'tabletop_frame', 'throw_pillow', 'top', 'top_panel', 'vertical_divider_panel', 'vertical_side_panel', 'vertical_side_panel2', 'wall_mount', 'wheel', 'wire','none']
material = ['Nvidia.vMaterials.AEC.Metal.Metal_Brushed_Herringbone.metal_brushed_herringbone_bricks_steel', 'Nvidia.vMaterials.AEC.Stone.Marble.Veined_Marble.veined_marble_gold_and_charcoal', 'Nvidia.vMaterials.Design.Ceramic.Porcelain_Floral.porcelain_floral_black', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_red', 'Nvidia.vMaterials.AEC.Wood.Bamboo.bamboo_carbonized_matte', 'Green Glass', 'Nvidia.vMaterials.AEC.Wood.Birch.birch_bleached_matte', 'Nvidia.vMaterials.Design.Ceramic.Porcelain_Floral.porcelain_floral_redgold', 'Nvidia.vMaterials.AEC.Wood.Oak.oak_rustic_matte', 'Nvidia.vMaterials.Design.Ceramic.Porcelain.porcelain_sand', 'Nvidia.vMaterials.Design.Ceramic.Porcelain_Floral.porcelain_floral_bluesilver', 'Nvidia.vMaterials.AEC.Stone.Marble.Imperial_Marble.stone_imperial_marble_copper_tones', 'Nvidia.vMaterials.Design.Leather.Leather_Snake.leather_snake_black', 'Nvidia.vMaterials.Design.Wood.Teak.teak_carbonized_matte', 'Nvidia.vMaterials.Design.Leather.Leather_Pebbled.pebbled_1', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_violet', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Yellow', 'Nvidia.vMaterials.AEC.Wood.white_oak_floorboards.white_oak_floorboards', 'Crackle_Bromine_SW-017-F844', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Light_Blue', 'Blue iron', 'Nvidia.vMaterials.Design.Fabric.Flannel.flannel_blueblack', 'Nvidia.vMaterials.AEC.Stone.Marble.Veined_Marble.veined_marble_copper_and_sunset', 'Rough Bronze', 'Brushed copper', 'Nvidia.vMaterials.AEC.Stone.Marble.Veined_Marble.veined_marble_gold_and_emerald', 'Nvidia.vMaterials.AEC.Wood.birch_wood_oiled.birch_wood_oiled', 'Nvidia.vMaterials.Design.Wood.burlwood.burlwood', 'Nvidia.vMaterials.AEC.Stone.Marble.Veined_Marble.veined_marble_silver_and_dapple_gray', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_sky_blue', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Dark_Red', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_midblue', 'Leaf Green', 'Nvidia.vMaterials.Design.Metal.diamond_plate.diamond_plate', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_ebony', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_brown', 'Nvidia.vMaterials.AEC.Metal.Metal_Patina_Hammered_Bricks.metal_patina_hammered_bricks_pearl', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_purple', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_green', 'Nvidia.vMaterials.Design.Fabric.Flannel.flannel_redblack', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_sapphirenvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_sapphire', 'Nvidia.vMaterials.AEC.Metal.Metal_Aged_Quilted_Backsplash.metal_aged_quilted_backsplash_antique_bronze', 'Glass', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_dark_blue', 'Grey_with_Gold_Crackled', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_black', 'Nvidia.vMaterials.AEC.Wood.Cherry.cherry_chocolate_coated', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_black', 'Nvidia.vMaterials.AEC.Wood.Oak.oak_mahogany_coated', 'Nvidia.vMaterials.AEC.Metal.Metal_Brushed_Disc_Mosaic.metal_brushed_disc_mosaic_silver', 'Nvidia.vMaterials.Design.Wood.Teak.teak_ebony_coated', 'Nvidia.vMaterials.Design.Ceramic.Porcelain_Cracked.cracked_porcelain_beige', 'Nvidia.vMaterials.AEC.Metal.Metal_Pitted_Steel.pitted_steel', 'Mirror', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_lime_green', 'Nvidia.vMaterials.AEC.Wood.Oak.oak_ebony_coated', 'Nvidia.vMaterials.Design.Leather.Leather_Snake.leather_snake_eggshell', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven_Cheery_Red', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_emerald', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_dark_gray', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_black', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Petrol', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_orange', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_red', 'Nvidia.vMaterials.AEC.Wood.Maple_Isometric_Parquet.maple_isometric_parquet_timber_wolf', 'Nvidia.vMaterials.AEC.Metal.Metal_Hammered_Bricks.metal_hammered_bricks_pearl', 'Antique Gold', 'Nvidia.vMaterials.AEC.Stone.Marble.River_Marble.river_marble_rust', 'Nvidia.vMaterials.Design.Fabric.Denim.denim_lightblue', 'Dented gold', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_green', 'Nvidia.vMaterials.Design.Metal.bare_metal.bare_metal', 'Nvidia.vMaterials.AEC.Wood.Beech.beech_ebony_oiled', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven_Orange', 'Nvidia.vMaterials.Design.Metal.Cast_Metal.cast_metal_copper_vein', 'Nvidia.vMaterials.Design.Leather.Upholstery.leather_upholstery_brown', 'Rough silver', 'Nvidia.vMaterials.AEC.Metal.Metal_Prisma_Tiles.metal_prisma_tiles_yellow_gold', 'Nvidia.vMaterials.AEC.Wood.Beech.beech_carbonized_oiled', 'Nvidia.vMaterials.AEC.Wood.Bamboo.bamboo_natural_oiled', 'Nvidia.vMaterials.AEC.Wood.Laminate_Oak.oak_hazelnut', 'Nvidia.vMaterials.Design.Leather.Upholstery.leather_upholstery_tan', 'Nvidia.vMaterials.AEC.Wood.Maple_Fan_Parquet.maple_fan_parquet_shades_of_gray_matte', 'Nvidia.vMaterials.AEC.Wood.Beech.beech_bleached_matte', 'Glass_Reflective', 'Nvidia.vMaterials.Design.Leather.Upholstery.leather_upholstery_darkgray', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_blue', 'Nvidia.vMaterials.AEC.Wood.Cherry.cherry_ebony_matte', 'Nvidia.vMaterials.Design.Metal.Cast_Metal.cast_metal_antique_nickel', 'Nvidia.vMaterials.AEC.Wood.Bamboo.bamboo_ash_coated', 'Nvidia.vMaterials.AEC.Wood.Laminate_Oak_2.Laminate_Oak_Slight_Smudges', 'Nvidia.vMaterials.Design.Leather.Suede.suede_black', 'Nvidia.vMaterials.AEC.Wood.Maple_Chevron_Parquet.maple_chevron_parquet_golden_honey_varnish', 'Nvidia.vMaterials.Design.Ceramic.Porcelain_Cracked.cracked_porcelain_gold_veined', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_beige', 'Nvidia.vMaterials.AEC.Stone.Marble.Classic_Marble.classic_marble_black_and_white', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven_Dark_Red', 'Nvidia.vMaterials.AEC.Wood.Maple_Inlaid_Parquet.maple_inlaid_parquet_rich_coffee', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_navyblue', 'Nvidia.vMaterials.AEC.Wood.Maple_Herringbone_Parquet.maple_herringbone_parquet_rich_coffee', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Cheery_Red', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_ruby', 'Nvidia.vMaterials.AEC.Wood.Wood_Bark.Wood_Bark', 'Nvidia.vMaterials.Design.Metal.gun_metal.gun_metal', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_yellow', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Dark_Green', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_orange', 'Black Glass', 'Nvidia.vMaterials.Design.Ceramic.Porcelain.porcelain_red', 'Nvidia.vMaterials.AEC.Metal.metal_beams.metal_beams', 'Nvidia.vMaterials.AEC.Metal.Metal_Patina_Hammered.metal_patina_hammered_darkened_silver', 'Nvidia.vMaterials.Design.Leather.Leather_Pebbled.pebbled_2', 'Nvidia.vMaterials.AEC.Wood.Wood_Cork.Wood_Cork', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_white', 'Nvidia.vMaterials.AEC.Wood.mahogany_floorboards.mahogany_floorboards', 'Nvidia.vMaterials.AEC.Metal.Metal_Modern_Stacked_Panels.metal_modern_stacked_panels_titanium', 'Nvidia.vMaterials.AEC.Wood.beech_wood_matte.beech_wood_matte', 'Nvidia.vMaterials.AEC.Wood.Maple_Tesselated_Parquet.maple_tessellated_parquet_ivory', 'Nvidia.vMaterials.AEC.Wood.Maple_Double_Herringbone_Parquet.maple_double_herringbone_parquet_mahogany_varnish', 'Nvidia.vMaterials.Design.Leather.Suede.suede_brown', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven', 'Nvidia.vMaterials.Design.Leather.Textured.leather_textured_black', ' nvidia.vMaterials.AEC.Metal.Metal_Aged_Disc_Mosaic.metal_aged_disc_mosaic_antique_copper', 'Nvidia.vMaterials.Design.Fabric.Fabric_Cotton_Fine_Woven.Fabric_Cotton_Fine_Woven_Orange', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven_Dark_Ash', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_blue', 'Nvidia.vMaterials.Design.Fabric.Denim.denim_darkblue', 'Gold metal', 'Nvidia.vMaterials.Design.Fabric.Stripes.fabric_stripes_blue', 'Nvidia.vMaterials.AEC.Wood.bamboo_coated.bamboo_coated', 'Nvidia.vMaterials.Design.Fabric.Felt.felt_red', 'Nvidia.vMaterials.AEC.Metal.Metal_Hammered_Bricks.metal_hammered_bricks_pale_gold', 'Nvidia.vMaterials.AEC.Metal.Metal_brushed_antique_copper_patinated.brushed_antique_copper_minimal_patina', 'Nvidia.vMaterials.AEC.Wood.Maple_Inlaid_Parquet.maple_inlaid_parquet_natural_mix', 'Nvidia.vMaterials.Design.Plastic.Plastic_Thick_Translucent_Flakes.plastic_lemon', 'Nvidia.vMaterials.Design.Leather.Textured.leather_textured_beige', 'Nvidia.vMaterials.AEC.Metal.Metal_Modern_Offset_Panels.metal_modern_offset_panels_carbon_steel', 'Nvidia.vMaterials.Design.Ceramic.Porcelain.porcelain_green', 'Nvidia.vMaterials.AEC.Wood.maple_wood_coated.maple_wood_coated', 'Acrylic', 'Nvidia.vMaterials.AEC.Wood.Maple.maple_ash_coated', 'Nvidia.vMaterials.Design.Metal.metal_cast_iron.metal_cast_iron', 'Nvidia.vMaterials.Design.Leather.Suede.suede_gray', 'Nvidia.vMaterials.AEC.Wood.Maple_Hexagon_Parquet.maple_hexagon_parquet_rough_ivory_varnish', 'Nvidia.vMaterials.AEC.Metal.Metal_brushed_antique_copper.brushed_antique_copper_shiny', 'Nvidia.vMaterials.Design.Leather.Textured.leather_textured_darkbrown', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_clear', 'Nvidia.vMaterials.AEC.Wood.Maple_Isometric_Parquet.maple_isometric_parquet_rustic_mix', 'Shiny Nickel', 'Nvidia.vMaterials.AEC.Stone.Marble.Veined_Marble.veined_marble_silver_and_storm', 'Nvidia.vMaterials.Design.Fabric.Flannel.flannel_blackgray', 'Nvidia.vMaterials.AEC.Stone.Marble.Large_Quartz_And_Marble.large_quartz_marble_coated_amber', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven', 'Nvidia.vMaterials.Design.Fabric.Cotton_Roughly_Woven.Fabric_Cotton_Roughly_Woven_Green', 'Nvidia.vMaterials.AEC.Wood.cherry_wood_oiled.cherry_wood_oiled']
material = [i.lower() for i in material]
objs =  ['bench', 'planter', 'dresser', 'stool', 'chair', 'cabinet', 'shelf', 'love seat', 'table', 'ottoman', 'vase', 'bed', 'trolley', 'sofa', 'lamp','none']



def sa_create(name, var):
    x = SA.create(name, var.shape, dtype=float)
    x[...] = var[...]
    x.flags.writeable = False
    return x


def make_weights_for_balanced_classes(images, nclasses):
    count = [0] * nclasses
    for item in images:
        count[item[1]] += 1
    weight_per_class = [0.] * nclasses
    N = float(sum(count))
    for i in range(nclasses):
        weight_per_class[i] = N / float(count[i])
    weight = [0] * len(images)
    for idx, val in enumerate(images):
        weight[idx] = weight_per_class[val[1]]
    return weight


def collation_fn(batch):
    """

    :param batch:
    :return:   coords_batch: N x 4 (x,y,z,batch)

    """
    coords, feats, labels = list(zip(*batch))

    for i in range(len(coords)):
        coords[i][:, 0] *= i

    return torch.cat(coords), torch.cat(feats), torch.cat(labels)


def collation_fn_eval_all(batch):
    """
    :param batch:
    :return:   coords_batch: N x 4 (x,y,z,batch)

    """
    coords, feats, labels, inds_recons = list(zip(*batch))
    inds_recons = list(inds_recons)
    # pdb.set_trace()

    accmulate_points_num = 0
    for i in range(len(coords)):
        coords[i][:, 0] *= i
        inds_recons[i] = accmulate_points_num + inds_recons[i]
        accmulate_points_num += coords[i].shape[0]

    return torch.cat(coords), torch.cat(feats), torch.cat(labels), torch.cat(inds_recons)


import numpy as np
from torch.utils.data import Dataset

N_POINTS = 1024


def pc_normalize(pc):
    l = pc.shape[0]
    centroid = np.mean(pc, axis=0)
    pc = pc - centroid
    m = np.max(np.sqrt(np.sum(pc ** 2, axis=1)))
    pc = pc / m
    return pc


class ObjectDataset(Dataset):
    def __init__(self, data_dict: dict, type: str, class_to_idx, n_points=N_POINTS):
        # Create a list of objects
        self.part_pc = data_dict[type]['pc']
        self.part_labels = data_dict[type]['labels']
        self.seg = data_dict[type]['seg']
        self.model_ids = data_dict[type]['model_ids']
        assert len(self.part_labels) == len(self.part_pc)

        self.part_label_to_idx = class_to_idx
        self.n_points = n_points

    def __getitem__(self, index):
        part_pc = self.part_pc[index]
        part_pc_label = self.part_labels[index]
        segment = self.seg[index]
        # model_class = self.model_class[index]

        idx = np.random.choice(np.arange(0, part_pc.shape[0]), self.n_points,
                               replace=self.n_points > part_pc.shape[0])
        model_ids = self.model_ids[index]
        # return {
        #     'pc': pc_normalize(part_pc[idx]),
        #     'label': self.part_label_to_idx[part_pc_label], # TODO-5 uncomment this line
        # }
        return pc_normalize(part_pc[idx]), self.part_label_to_idx[part_pc_label], segment[idx], model_ids

    def __len__(self):
        return len(self.part_pc)


class ScanNet3D(data.Dataset):
    # Augmentation arguments
    SCALE_AUGMENTATION_BOUND = (0.9, 1.1)
    ROTATION_AUGMENTATION_BOUND = ((-np.pi / 64, np.pi / 64), (-np.pi / 64, np.pi / 64), (-np.pi,
                                                                                          np.pi))
    TRANSLATION_AUGMENTATION_RATIO_BOUND = ((-0.2, 0.2), (-0.2, 0.2), (0, 0))
    ELASTIC_DISTORT_PARAMS = ((0.2, 0.4), (0.8, 1.6))

    ROTATION_AXIS = 'z'
    LOCFEAT_IDX = 2

    def __init__(self, dataPathPrefix='Data', voxelSize=0.05,
                 split='train', aug=False, memCacheInit=True, identifier=1233, loop=1,
                 data_aug_color_trans_ratio=0.1, data_aug_color_jitter_std=0.05, data_aug_hue_max=0.5,
                 data_aug_saturation_max=0.2, eval_all=False
                 ):
        super(ScanNet3D, self).__init__()
        self.split = split
        self.identifier = identifier
        # self.data_paths = sorted(glob(join(dataPathPrefix, split, '*.pth')))
        self.data_paths = sorted(glob(join(dataPathPrefix, '*.glb')))

        self.voxelSize = voxelSize
        self.aug = aug
        self.loop = loop
        self.eval_all = eval_all
        self.voxelizer = Voxelizer(
            voxel_size=voxelSize,
            clip_bound=None,
            use_augmentation=True,
            scale_augmentation_bound=self.SCALE_AUGMENTATION_BOUND,
            rotation_augmentation_bound=self.ROTATION_AUGMENTATION_BOUND,
            translation_augmentation_ratio_bound=self.TRANSLATION_AUGMENTATION_RATIO_BOUND)

        if aug:
            prevoxel_transform_train = [t.ElasticDistortion(self.ELASTIC_DISTORT_PARAMS)]
            self.prevoxel_transforms = t.Compose(prevoxel_transform_train)
            input_transforms = [
                t.RandomHorizontalFlip(self.ROTATION_AXIS, is_temporal=False),
                t.ChromaticAutoContrast(),
                t.ChromaticTranslation(data_aug_color_trans_ratio),
                t.ChromaticJitter(data_aug_color_jitter_std),
                t.HueSaturationTranslation(data_aug_hue_max, data_aug_saturation_max),
            ]
            self.input_transforms = t.Compose(input_transforms)
        with open("data/newid_{}.txt".format(split), "r") as f:
            model_ids = f.readlines()

        # model_ids = defaultdict(list)
        # with open("/ibex/scratch/liy0r/cvpr/BPNet/split.txt", "r") as f:
        #     for line in f:
        #         ids, label = line.rstrip().split(',')
        #         model_ids[label].append(ids)
        #
        # self.data_paths = model_ids[split]

        self.length = len(self.data_paths)

        # Part Name:

        with open("data/parts_annotation.json") as f:
            self.new_part_names = json.load(f)
        part_set = set()
        with open("data/newid.txt".format(split), "r") as f:
            allids = f.readlines()
        allmodel = []
        for i in allids:
            allmodel.append(i.strip())
        for i in self.new_part_names.keys():
            if i in allmodel:
                for j in self.new_part_names[i].values():
                    part_set.add(j)


        self.part_map = dict()
        self.part_map['background'] = 0
        for i, j in enumerate(sorted(list(part_set))):
            self.part_map[j] = i + 1
        # self.part_ids = {}
        # model_ids = []
        print("our part number is here", len(part_set))
        print(self.length, "here are the sizes of dataset {}".format(split))
        # print("")
        if memCacheInit and (not exists("/dev/shm/wbhu_scannet_3d_%s_%06d_locs_%08d" % (split, identifier, 0))):
            print('[*] Starting shared memory init ...')
            all_models = pd.read_csv('data/products_all.csv')
            total_models = len(all_models)
            print("Reading {} models".format(total_models))

            with open('data/models_to_be_used.json') as fin:
                models_to_included = json.load(fin)
            print(len(self.new_part_names.keys()))

            def should_be_included(record):
                model_id = record['product_id']
                return model_id in models_to_included

            # all_models = all_models[all_models.apply(should_be_included, axis=1)]
            WORKING_DIR = dataPathPrefix
            indexs = []
            j = 0

            for i, model_id in enumerate(model_ids):
                # for i, model_id in enumerate(list(all_models.product_id)):
                # print(model_id)
                # if model_id not in new_part_names and model_id not in model_ids:
                model_id = model_id[:-1]
                if model_id not in self.new_part_names:
                    continue
                gltf_path = '{}/{}.glb'.format(WORKING_DIR, model_id)
                try:
                    gltf_stats = os.stat(gltf_path)
                    model_size = gltf_stats.st_size / 1024000
                except:
                    print("model can't found {}".format(model_id))
                    continue
                # print('Model:{} is of size {}'.format(model_id, model_size))
                # return model_id, None
                #
                if model_size < 0.09:  # Ignore extremely small (corrupted) models
                    print("Error reading2")
                    print("Model:{}, Failed!".format(model_id))
                    continue
                    # return model_id, None

                # Try to sample now
                try:
                    mesh = trimesh.load(gltf_path)
                    print("read successfully")
                except:
                    print("Error in reading")
                    continue
                    # print("Model:{}, Failed!".format(model_id))
                    # return model_id, None
                colors = {}
                v = {}
                segment = {}
                for g_name, g_mesh in mesh.geometry.items():
                    try:
                        new_part_name = self.new_part_names[model_id][g_name]
                        v[g_name] = np.asarray(trimesh.sample.sample_surface(g_mesh, N_POINTS_PER_PART)[0])
                        colors[g_name] = np.ones_like(v[g_name])
                        segment[g_name] = np.full(colors[g_name].shape[0], self.part_map[new_part_name])
                    except:
                        try:

                            for p in self.new_part_names[model_id].keys():
                                if p in g_name:
                                    new_name = p
                                    break
                            new_part_name = self.new_part_names[model_id][new_name]

                            # FOR STYLE MODEL WE USE THIS COLOR, FOR NON STYLE MODEL WE USE 1
                            # colors[g_name] = np.asarray(mesh.geometry[g_name].visual.to_color().vertex_colors)
                            v[g_name] = np.asarray(trimesh.sample.sample_surface(g_mesh, N_POINTS_PER_PART)[0])
                            colors[g_name] = np.ones_like(v[g_name])
                            segment[g_name] = np.full(colors[g_name].shape[0], self.part_map[new_part_name])
                        except:
                            print(model_id)
                            print(g_name)
                            print(self.new_part_names[model_id])
                a = []
                for key in v.keys():
                    a.append(np.hstack((v[key], colors[key], np.expand_dims(segment[key], axis=1))))
                b = np.vstack(a)
                sa_create("shm://wbhu_scannet_3d_%s_%06d_locs_%08d" % (split, identifier, j), b[:, :3])
                sa_create("shm://wbhu_scannet_3d_%s_%06d_feats_%08d" % (split, identifier, j), b[:, 3:6])
                sa_create("shm://wbhu_scannet_3d_%s_%06d_labels_%08d" % (split, identifier, j), b[:, 6])
                indexs.append(model_id)
                j += 1

            # with open("data/newid_{}.txt".format(split), "r") as f:
            #     model_ids = f.readlines()
            # newmodel = []
            # for i in model_ids:
            #     newmodel.append(i.strip())
            self.data_paths = indexs
            with open("indexs1_{}.txt".format(split), "w") as f:
                for i in indexs:
                    f.write(i + "\n")


        print('[*] %s (%s) loading done (%d)! ' % (dataPathPrefix, split, self.length))

    def __getitem__(self, index_long):
        index = index_long % self.length
        locs_in = SA.attach("shm://wbhu_scannet_3d_%s_%06d_locs_%08d" % (self.split, self.identifier, index)).copy()
        feats_in = SA.attach("shm://wbhu_scannet_3d_%s_%06d_feats_%08d" % (self.split, self.identifier, index)).copy()
        labels_in = SA.attach("shm://wbhu_scannet_3d_%s_%06d_labels_%08d" % (self.split, self.identifier, index)).copy()
        locs = self.prevoxel_transforms(locs_in) if self.aug else locs_in
        locs, feats, labels, inds_reconstruct = self.voxelizer.voxelize(locs, feats_in, labels_in)
        if self.eval_all:
            labels = labels_in
        if self.aug:
            locs, feats, labels = self.input_transforms(locs, feats, labels)
        coords = torch.from_numpy(locs).int()
        coords = torch.cat((torch.ones(coords.shape[0], 1, dtype=torch.int), coords), dim=1)
        feats = torch.from_numpy(feats).float() / 127.5 - 1.
        labels = torch.from_numpy(labels).long()

        if self.eval_all:
            return coords, feats, labels, torch.from_numpy(inds_reconstruct).long()
        return coords, feats, labels

    def __len__(self):
        return self.length


if __name__ == '__main__':
    import time, random
    from tensorboardX import SummaryWriter

    # data_root = '/research/dept6/wbhu/Dataset/ScanNet'
    data_root = '/data/dataset/scannetv2'
    train_data = ScanNet3D(dataPathPrefix=data_root, aug=True, split='train', memCacheInit=True, voxelSize=0.05)
    val_data = ScanNet3D(dataPathPrefix=data_root, aug=False, split='val', memCacheInit=True, voxelSize=0.05,
                         eval_all=True)

    manual_seed = 123


    def worker_init_fn(worker_id):
        random.seed(manual_seed + worker_id)


    random.seed(manual_seed)
    np.random.seed(manual_seed)
    torch.manual_seed(manual_seed)
    torch.cuda.manual_seed_all(manual_seed)

    train_loader = torch.utils.data.DataLoader(train_data, batch_size=2, shuffle=True, num_workers=4, pin_memory=True,
                                               worker_init_fn=worker_init_fn, collate_fn=collation_fn)
    val_loader = torch.utils.data.DataLoader(val_data, batch_size=2, shuffle=False, num_workers=4, pin_memory=True,
                                             worker_init_fn=worker_init_fn, collate_fn=collation_fn_eval_all)
    trainLog = SummaryWriter('Exp/scannet/statistic/train')
    valLog = SummaryWriter('Exp/scannet/statistic/val')

    for idx in range(1):
        end = time.time()
        for step, (coords, feat, label) in enumerate(train_loader):
            print(
                'time: {}/{}--{}'.format(step + 1, len(train_loader), time.time() - end))
            trainLog.add_histogram('voxel_coord_x', coords[:, 0], global_step=step)
            trainLog.add_histogram('voxel_coord_y', coords[:, 1], global_step=step)
            trainLog.add_histogram('voxel_coord_z', coords[:, 2], global_step=step)
            trainLog.add_histogram('color', feat, global_step=step)
            # time.sleep(0.3)
            end = time.time()

        for step, (coords, feat, label, inds_reverse) in enumerate(val_loader):
            print(
                'time: {}/{}--{}'.format(step + 1, len(val_loader), time.time() - end))
            valLog.add_histogram('voxel_coord_x', coords[:, 0], global_step=step)
            valLog.add_histogram('voxel_coord_y', coords[:, 1], global_step=step)
            valLog.add_histogram('voxel_coord_z', coords[:, 2], global_step=step)
            valLog.add_histogram('color', feat, global_step=step)
            # time.sleep(0.3)
            end = time.time()

    trainLog.close()
    valLog.close()
