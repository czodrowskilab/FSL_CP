import numpy as np
import pandas as pd
import torch
import torchvision
import torch.nn as nn
import torch.backends.cudnn as cudnn
import timm
import os

from torch.utils import data
from torch.utils.data import Dataset
from torchvision import models, transforms
from timm.data.dataset import ImageDataset
from tqdm import tqdm







class npzimages(Dataset):
    """Converts .npz images from sorted datafolder to numpy arrays and applies transforms.
    
    Is a subclass from torch.utils.data.Dataset which is only ment to apply transforms to the numpy array of a given .npz image"""
    
    def __init__(self, img_dir, transform=None):
        super().__init__()
        self.img_dir = img_dir
        self.transform = transform
        self.filenames = sorted(os.listdir(f'{self.img_dir}'))
    

    def __len__(self):
        """Returns the length of the dataset"""
        return len(os.listdir(f'{self.img_dir}'))

    
    def __getitem__(self, idx):
        """Loads .npz images as numpy array.
        
        Keyword arguments:
        idx -- index of image in dataset
        """
        self.filename = self.filenames[idx]  
        image = np.load(f'{self.img_dir}/{self.filename}')['sample']
        filename = self.filename.rsplit('-',1)[0]
       
        
        if self.transform:
            image = self.transform(image)
            
        return image, filename
    





device = torch.device("cuda:3" if torch.cuda.is_available() else "cpu")



testdict = {'in_chans':5, 'embedding_size':1000, 'model_name':'resnet50', 'device':device}

model = timm.create_model('resnet50', pretrained=True, in_chans=5)


for param in model.parameters():
    param.requires_grad = False

# Parameters of newly constructed modules have requires_grad=True by default
num_ftrs = model.fc.in_features
embedding_size = 1000
model.fc = nn.Linear(num_ftrs, embedding_size)

model = model.to(device)



def create_embedding(path_data, transforms, model, embedding_size, batch_size=1,):
    """Feeds the given data to a pretrained model and returns an embedding of a given size.
    
    Keyword arguments:
    path_data -- path of the folder that contains the data in form of .npz images
    transforms -- transform operations ( for multipls transforms use transforms.Compose(list of transform operations))
    model -- pretrained model
    batch_size -- batch size of the image array; this should be 1!
    embedding_size -- size of the created embedding"""
    
    images = npzimages(path_data, transforms)
    
    dataloader = torch.utils.data.DataLoader(images, batch_size=batch_size)
    
    
    df_output = pd.DataFrame(columns=['SAMPLE_KEY'])

    
   #counter initialisation
    output_old = torch.zeros((1,embedding_size)).to(device)
    view_counter = 0
    indexdf = 0
    
    #set filename_old as first filename in dir
    _, filename = next(enumerate(dataloader))
    filename_old = filename[1][0]
    
    
    counter = 0 
    for image in tqdm(dataloader):
        
        
        
        filename = image[1][0]
        
        
        image = image[0]
        image = image.to(device)
    
       #model input
        output = model(image)
        
        
      
        if filename == filename_old:
            
            view_counter += 1
            sum_tensors = torch.add(output,output_old)
            output_old = sum_tensors
            filename_old = filename
            
        elif filename != filename_old:
            
            num_views = view_counter
            
            output_mean = torch.div(output_old,num_views)
            
            output_mean = output_mean.cpu().detach().numpy()
            
            #convert output mean to pandas row add to df
            
            
            
            df_temp = pd.DataFrame(output_mean.reshape(1,-1))
            df_output = pd.concat([df_output,df_temp], axis=0, ignore_index=True)
            df_output.loc[indexdf,'SAMPLE_KEY'] = filename_old
            indexdf+=1
            
            output_old = torch.zeros((1,embedding_size)).to(device)
            view_counter = 0
            
            
           
            
            view_counter += 1
            sum_tensors = torch.add(output,output_old)
            output_old = sum_tensors
            filename_old = filename
            
            
        
        if counter==(len(dataloader)-1):
            
            view_counter += 1
            sum_tensors = torch.add(output,output_old)
            output_old = sum_tensors
            
            num_views = view_counter
            
            output_mean = torch.div(output_old,num_views)
            
            output_mean = output_mean.cpu().detach().numpy()
            
            df_temp = pd.DataFrame(output_mean.reshape(1,-1))
            df_output = pd.concat([df_output,df_temp], axis=0, ignore_index=True)
            df_output.loc[indexdf,'SAMPLE_KEY'] = filename          
                        
        counter += 1
       
    
    return df_output

transforms_list = transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406, 0.450, 0.430], [0.229, 0.224, 0.225, 0.226, 0.222]) ])



df_test = create_embedding('/mnt/scratch/Son_cellpainting/my_cp_images', transforms_list, model, 1000)

######dataoutput#####

norm_cp_df = pd.read_csv('/home/son.ha/FSL_CP/data/output/norm_CP_feature_df.csv').iloc[:, [0,1,5]]
label_df = pd.read_csv('/home/son.ha/FSL_CP/data/output/FINAL_LABEL_DF.csv')

label_df = label_df.drop_duplicates(subset='SAMPLE_KEY').iloc[:, 0:4]
label_df['SAMPLE_KEY']=label_df['SAMPLE_KEY'].astype('string')
label_df = label_df.iloc[:, 2:4]

bre = df_test.pop('SAMPLE_KEY')
df_test.insert(0,'SAMPLE_KEY', bre)



norm_cp_df = pd.merge(norm_cp_df, label_df,how='left')
df_final = pd.merge(norm_cp_df, df_test,how='left').fillna(0)
df_final.to_csv('/home/son.ha/FSL_CP/data/output/cnn_embeddings.csv', index=False)