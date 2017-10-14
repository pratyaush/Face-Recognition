from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from scipy import misc
import tensorflow as tf
import numpy as np
import sys
import time
import os
import argparse
import facenet
import align.detect_face

def main(args):

     dataset = facenet.get_dataset(args.data_dir)
     # Check that there are at least one training image per class
     for cls in dataset:
         assert len(cls.image_paths)>0, 'There must be at least one image for prediction' 

     paths, labels = facenet.get_image_paths_and_labels(dataset)

     
     
     with tf.Graph().as_default():

        with tf.Session() as sess:
            
            st = time.time()
            images = load_and_align_data(paths, args.image_size, args.margin, args.gpu_memory_fraction)
            print('Load and Align Images time = {}'.format(time.time() - st))
            print(' ')
            
            # Load the model
            facenet.load_model(args.model)
            print('Load model time = {}'.format(time.time() - st))
            print(' ')
            # Get input and output tensors
            images_placeholder = tf.get_default_graph().get_tensor_by_name("input:0")
            embeddings = tf.get_default_graph().get_tensor_by_name("embeddings:0")
            phase_train_placeholder = tf.get_default_graph().get_tensor_by_name("phase_train:0")

            # Run forward pass to calculate embeddings
            feed_dict = { images_placeholder: images, phase_train_placeholder:False }
            emb = sess.run(embeddings, feed_dict=feed_dict)
            print('Feature Extraction time = {}'.format(time.time() - st))            
            print(' ')
 
            emb_array=np.load('embed.npy')
            labels=np.load('labels.npy')
            class_names=np.load('classnames.npy')
            
            nrof_embeds = labels.size
            nrof_images = len(paths)
           
            dist_array = np.zeros((nrof_embeds, nrof_images))

            for i in range(nrof_embeds):
                for j in range(nrof_images):
                    dist = np.sqrt(np.sum(np.square(np.subtract(emb_array[i,:], emb[j,:]))))
                    dist_array[i][j] = dist

            print('Distance Calculation time = {}'.format(time.time() - st))
            print(' ')
            pred_array = dist_array.argmin(0) 
         
            pred_label_array=  np.zeros(len(labels))
            Unknown = 0
          
            for i in range(len(pred_array)):
                if dist_array[pred_array[i]][i] < 0.75 :
                    pred_label = labels[pred_array[i]]
                    pred_label_array[int(pred_label)] +=1
                    #print(pred_array)
                    #print(pred_label)
                
                else : 
                    Unknown +=1

            pred_label = pred_label_array.argmax() 
            
            if(pred_label_array[pred_label]>Unknown):
                pred_face = class_names[int(pred_label)]
            else:
                pred_face = 'Unknown'
            
            print('Face identified as:')
            print(pred_face)
            print(' ')
            #print('Face Distance:')
            #print(dist_array[pred_array[i]][i])            
            #print(' ')
           
            print('Elapsed total time = {}'.format(time.time() - st))
            print(' ')
            
            
def load_and_align_data(image_paths, image_size, margin, gpu_memory_fraction):

    minsize = 20 # minimum size of face
    threshold = [ 0.6, 0.7, 0.7 ]  # three steps's threshold
    factor = 0.709 # scale factor
    
    print('Creating networks and loading parameters')
    with tf.Graph().as_default():
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=gpu_memory_fraction)
        sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options, log_device_placement=False))
        with sess.as_default():
            pnet, rnet, onet = align.detect_face.create_mtcnn(sess, None)
  
    nrof_samples = len(image_paths)
    img_list = [None] * nrof_samples
    for i in range(nrof_samples):
        img = misc.imread(os.path.expanduser(image_paths[i]))
        img_size = np.asarray(img.shape)[0:2]
        bounding_boxes, _ = align.detect_face.detect_face(img, minsize, pnet, rnet, onet, threshold, factor)
        det = np.squeeze(bounding_boxes[0,0:4])
        bb = np.zeros(4, dtype=np.int32)
        bb[0] = np.maximum(det[0]-margin/2, 0)
        bb[1] = np.maximum(det[1]-margin/2, 0)
        bb[2] = np.minimum(det[2]+margin/2, img_size[1])
        bb[3] = np.minimum(det[3]+margin/2, img_size[0])
        cropped = img[bb[1]:bb[3],bb[0]:bb[2],:]
        aligned = misc.imresize(cropped, (image_size, image_size), interp='bilinear')
        prewhitened = facenet.prewhiten(aligned)
        img_list[i] = prewhitened
    images = np.stack(img_list)
    return images

def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    
    parser.add_argument('model', type=str, 
        help='Could be either a directory containing the meta_file and ckpt_file or a model protobuf (.pb) file')
    parser.add_argument('data_dir', type=str,
        help='Path to the data directory containing aligned LFW face patches.')
    parser.add_argument('--image_size', type=int,
        help='Image size (height, width) in pixels.', default=160)
    parser.add_argument('--seed', type=int,
        help='Random seed.', default=666)
    parser.add_argument('--margin', type=int,
        help='Margin for the crop around the bounding box (height, width) in pixels.', default=44)
    parser.add_argument('--gpu_memory_fraction', type=float,
        help='Upper bound on the amount of GPU memory that will be used by the process.', default=0.9)
    return parser.parse_args(argv)

if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))