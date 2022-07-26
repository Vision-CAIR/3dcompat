# 3D Shape Classification and Part Segmentation

This repo includes the code for 3d Shape Classification and Part Segmentation on 3DCoMPaT dataset using prevalent 3D vision algorithms, including [PointNet](http://openaccess.thecvf.com/content_cvpr_2017/papers/Qi_PointNet_Deep_Learning_CVPR_2017_paper.pdf), [PointNet++](http://papers.nips.cc/paper/7095-pointnet-deep-hierarchical-feature-learning-on-point-sets-in-a-metric-space.pdf), [DGCNN](https://arxiv.org/abs/1801.07829), [PCT](https://arxiv.org/pdf/2012.09688.pdf), and [PointMLP](https://arxiv.org/abs/2202.07123) in pytorch.

You can find the pretrained models and log files in [gdrive](https://drive.google.com/drive/folders/1k1TDDzNvfnnxd_F8PxlsPBmnrr11-I-w?usp=sharing).

## 1. Install
The latest codes are tested on Ubuntu 16.04, CUDA10.1, PyTorch 1.7 and Python 3.7:
```bash
conda install pytorch==1.7.0 cudatoolkit=10.1 -c pytorch
```

## 2. Data Preparation
Run the following script to prepare point cloud data.
```bash
python prepare_data.py
```

Or you can directly download our preprocessed data [3DCoMPaT](https://drive.google.com/drive/folders/1ZeX7sXaaumjaeI9UWrFAoHz8DO_ZcN-J?usp=sharing) and save in `data/`.

## 3. Classification (3DCoMPaT)

```bash
# 3DCoMPaT
# Select different models in ./models 

# e.g., pointnet2_ssg 
python train_classification.py --model pointnet2_cls_ssg --log_dir pointnet2_cls_ssg
python test_classification.py --log_dir pointnet2_cls_ssg
```

* Note that we use same data augmentations and training schedules for all comparing methods following [Pointnet_Pointnet2_pytorch](https://github.com/yanx27/Pointnet_Pointnet2_pytorch). We report performance on both validation and test sets.
### Performance (Instance average Accuracy)
| Model | Previous | Val | Test | Pretrained| 
|--|--|--|--|--|
| PointNet2_SSG  | - | 75.59 |73.78 | [gdrive](https://drive.google.com/drive/folders/1S9sdkk3m2rGTcOE8Iv1NY2CMDKskwRUo?usp=sharing) | 
| PointNet2_MSG  |  57.95| 78.15 | 74.70|  [gdrive](https://drive.google.com/drive/folders/1YkXI5ouvigcET-JycoUhprjSgaAyrTQE?usp=sharing) | 
| DGCNN  |  68.32| 71.36 | 74.64 | [gdrive](https://drive.google.com/drive/folders/12FWcSsqiTtVKoL_twynhmCPApdYD-sAa?usp=sharing) | 
| PCT  |  69.09 | 68.33 | 70.07| [gdrive](https://drive.google.com/drive/folders/1YAmNJrxiWRIyHpc2sSD828ELM-swyoFh?usp=sharing) | 
| PointMLP  |  - | 73.36 | 70.83| [gdrive](https://drive.google.com/drive/folders/1B5CPHuPQRsn3SmW5ZNo88JuVBR8fqYg8?usp=sharing) | 


## 4. Part Segmentation (3DCoMPaT)

```bash
# Check model in ./models 
# e.g., pointnet2_ssg
python train_partseg.py --model pointnet2_part_seg_ssg --log_dir pointnet2_part_seg_ssg
python test_partseg.py --log_dir pointnet2_part_seg_ssg
```

* Note that we use same data augmentations and training schedules for all comparing methods following [Pointnet_Pointnet2_pytorch](https://github.com/yanx27/Pointnet_Pointnet2_pytorch). We report performance on both validation and test sets.

### Performance (Accuracy)
| Model | Previous| Val | Test | Pretrained|
|--|--|--|--|--|
|PointNet2_SSG|24.18| 48.61 | 51.22| [gdrive](https://drive.google.com/drive/folders/1yoGpiwCxHM-cqE_T2s4RrH7XiMvbhjlu?usp=sharing) | 
|PCT | 37.37 | 41.19 | 48.43| [gdrive](https://drive.google.com/drive/folders/1X8fN1PXFqnFmoMY1EUwjRzWBJEiBbdwB?usp=sharing) | 

## 5. Sim2Rel:Transferring to ScanObjectNN
```bash
# Check model in ./models 
# e.g., pointnet2_ssg
python train_classification_sim2rel.py --model pointmlp --log_dir pointmlp_cls
python test_classification_sim2rel.py --log_dir pointmlp_cls
```
Note that we use same data augmentations and training schedules for all comparing methods following [Pointnet_Pointnet2_pytorch](https://github.com/yanx27/Pointnet_Pointnet2_pytorch). We report performance on the test set of ScanObjectNN.
### Performance (Accuracy)
| Model | Previous | Test| Pretrained|
|--|--|--|--|
|ModelNet40|24.33| 30.69| [gdrive](https://drive.google.com/drive/folders/155vEhpSTfBLbievkEKoEMA4ZW4t5CaHC?usp=sharing) | 
|3DCoMPaT | 29.21 | 28.49| [gdrive](https://drive.google.com/drive/folders/10jFftppEPvZzid0TXbWyqBovyQEPWBqa?usp=sharing) | 

This code repository is heavily borrowed from [Pointnet_Pointnet2_pytorch](https://github.com/yanx27/Pointnet_Pointnet2_pytorch), [DGCNN](https://github.com/WangYueFt/dgcnn), [PCT](https://github.com/Strawberry-Eat-Mango/PCT_Pytorch), and [PointMLP](https://github.com/ma-xu/pointMLP-pytorch).
