# 2D Shape Classification

We provide here details about the code for a simple 2D ResNet shape classifier trained on 3DCoMPaT.

### 0. Requirements
List of requirements:

- `numpy==1.22.3`
- `torch==1.10.2`
- `torchvision==0.12.0`
- `webdataset==0.2.5`

Additionally, the `compat2D.py` file in the [compat_api](../../compat_api/) directory must be added or linked to this folder:

```bash
ln -s ../../compat_api/compat2D.py .
```

### 1. Dataset
The dataset must be downloaded in the WebDataset format using our provided download script. `root_url` must point to the root folder for the WebDataset shards.

For example, if `root_url` resolves to `/root/my_path/../compat10/`, then `compat10/` must have the following structure:

```
compat10/
|______train/
        |______train_0000.tar
        |______train_0001.tar
        ...
        |______train_00XX.tar
|______val/
        |______val_0000.tar
        |______val_0001.tar
        ...
        |______val_00XX.tar
```

This is the default folder structure when downloading the dataset using our provided script.

### 2. Training
To start training, run the `main.py` script:

`python3 main.py [options]`

Parameters are as follows:

**Input/Output**
- `num-workers`: Number of subprocesses to use for the dataloader.
- `use-tmp`: Use local temporary cache when loading the dataset.
- `root-url`: Root URL for WebDataset shards (see [Datasets](#1-dataset))


**Dataset**
- `n-comp`: Total number of compositions to use for training and evaluation.
- `view-type`: Train on a specific view type (one of `canonical`, `random` or `all` (default)).


**Training**
- `batch-size`: Size of each batch (same for generation/filtering/training, default: 64).
- `weight-decay`: SGD Weight decay.
- `momentum`: SGD Momentum.

- `nepochs`: Number of epochs to train for.
- `resnet-type`: ResNet variant to be used for training, (one of `resnet10` or `resnet50`).
- `use-pretrained`: Use a model pre-trained on ImageNet.

- `resume`: Resume training with the last saved model.
- `seed`: Random seed.

**Output**

- `models-dir`: Output model directory to use to save models.

An example run is provided below, for a batch size of `64`, with `10` compositions while training on canonical views only from an ImageNet-pretrained ResNet50:

```
python main.py --num-workers 2 \
    --root-url https://3dcompat-dataset.s3-us-west-1.amazonaws.com/WDS/ \
    --models-dir out_dir \
    --batch-size 64 \
    --resnet-type resnet50 \
    --nepochs 1 \
    --seed 0 \
    --n-comp 10 \
	--use-pretrained \
    --view-type all
```

Note that `root_url` should be changed to the local path of 3DCoMPaT to avoid redownloading the dataset at training time.

### 3. Evaluation and pretrained models
We provide below pretrained models on various number of compositions, with their classiciation accuracies evaluated on the 3DCoMPaT **validation** set.

| Model | #Compositions | View type | Top-1 Acc. | Top-5 Acc. | Download |
|--|--|--|--|--|--|
|ResNet50 | 10 | Mixed | 80.0 | 95.6 | [resnet50](https://drive.google.com/file/d/1bmN_nE2tttTkcjG0U7RvFpX9Ol7DEnnP/view?usp=share_link) | 
