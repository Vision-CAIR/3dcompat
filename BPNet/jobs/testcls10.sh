#!/bin/bash

#SBATCH --job-name=3dtestbp2d #Your Job Name
#SBATCH --time=12:59:00 #Walltime: Duration for the Job to run HH:MM:SS
#SBATCH --error=compat3d-%J.err #The .error file name
#SBATCH --mem=128G
#SBATCH --gres=gpu:v100:4
#SBATCH --output=compat3d-%J.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=yuchen.li@kaust.edu.sa

#Go to your working directory
cd /ibex/scratch/liy0r/cvpr/BPNet
conda activate bpnet
source activate bpnet
sh tool/test.sh com10review config/scannet/bpnet_5cm_cls_style_new_10.yaml 4
