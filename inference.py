from glob import glob
import shutil
import torch
from time import  strftime
import os, sys, time
from argparse import ArgumentParser

from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff  
from src.facerender.animate import AnimateFromCoeff
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data
from src.utils.init_path import init_path

def main(args):
    #torch.backends.cudnn.enabled = False

    inference_startTime = time.time()
    pic_path = args.source_image
    audio_path = args.driven_audio
    save_dir = os.path.join(args.result_dir, strftime("%Y_%m_%d_%H.%M.%S"))
    os.makedirs(save_dir, exist_ok=True)
    pose_style = args.pose_style
    device = args.device
    batch_size = args.batch_size
    input_yaw_list = args.input_yaw
    input_pitch_list = args.input_pitch
    input_roll_list = args.input_roll
    ref_eyeblink = args.ref_eyeblink
    ref_pose = args.ref_pose

    current_root_path = os.path.split(sys.argv[0])[0]

    init_path_startTime = time.time()
    
    sadtalker_paths = init_path(args.checkpoint_dir, os.path.join(current_root_path, 'src/config'), args.size, args.old_version, args.preprocess)
    
    init_path_endTime = time.time()    
    execution_time = init_path_endTime - init_path_startTime
    print(f"init_path Execution Time: {execution_time} seconds")

    #init model
    CropAndExtract_startTime = time.time()
    preprocess_model = CropAndExtract(sadtalker_paths, device)
    CropAndExtract_endTime = time.time()    
    execution_time = CropAndExtract_endTime - CropAndExtract_startTime
    print(f"CropAndExtract Execution Time: {execution_time} seconds")


    Audio2Coeff_startTime = time.time()
    audio_to_coeff = Audio2Coeff(sadtalker_paths,  device)
    Audio2Coeff_endTime = time.time()    
    execution_time = Audio2Coeff_endTime - Audio2Coeff_startTime
    print(f"Audio2Coeff Execution Time: {execution_time} seconds")
    
    AnimateFromCoeff_startTime = time.time()
    animate_from_coeff = AnimateFromCoeff(sadtalker_paths, device)
    AnimateFromCoeff_endTime = time.time()    
    execution_time = AnimateFromCoeff_endTime - AnimateFromCoeff_startTime
    print(f"AnimateFromCoeff Execution Time: {execution_time} seconds")

    #crop image and extract 3dmm from image
    first_frame_dir = os.path.join(save_dir, 'first_frame_dir')
    os.makedirs(first_frame_dir, exist_ok=True)
    print('3DMM Extraction for source image')
    generate_startTime = time.time()
    first_coeff_path, crop_pic_path, crop_info =  preprocess_model.generate(pic_path, first_frame_dir, args.preprocess,\
                                                                             source_image_flag=True, pic_size=args.size)
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"CropAndExtract preprocess_model.generate Execution Time: {execution_time} seconds")
    
    
    if first_coeff_path is None:
        print("Can't get the coeffs of the input")
        return

    generate_startTime = time.time()
    if ref_eyeblink is not None:
        ref_eyeblink_videoname = os.path.splitext(os.path.split(ref_eyeblink)[-1])[0]
        ref_eyeblink_frame_dir = os.path.join(save_dir, ref_eyeblink_videoname)
        os.makedirs(ref_eyeblink_frame_dir, exist_ok=True)
        print('3DMM Extraction for the reference video providing eye blinking')
        ref_eyeblink_coeff_path, _, _ =  preprocess_model.generate(ref_eyeblink, ref_eyeblink_frame_dir, args.preprocess, source_image_flag=False)
    else:
        ref_eyeblink_coeff_path=None
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"CropAndExtract ref_eyeblink preprocess_model.generate Execution Time: {execution_time} seconds")

    generate_startTime = time.time()
    if ref_pose is not None:
        if ref_pose == ref_eyeblink: 
            ref_pose_coeff_path = ref_eyeblink_coeff_path
        else:
            ref_pose_videoname = os.path.splitext(os.path.split(ref_pose)[-1])[0]
            ref_pose_frame_dir = os.path.join(save_dir, ref_pose_videoname)
            os.makedirs(ref_pose_frame_dir, exist_ok=True)
            print('3DMM Extraction for the reference video providing pose')
            ref_pose_coeff_path, _, _ =  preprocess_model.generate(ref_pose, ref_pose_frame_dir, args.preprocess, source_image_flag=False)
    else:
        ref_pose_coeff_path=None

    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"CropAndExtract ref_pose preprocess_model.generate Execution Time: {execution_time} seconds")
    #audio2ceoff
    generate_startTime = time.time()
    batch = get_data(first_coeff_path, audio_path, device, ref_eyeblink_coeff_path, still=args.still)
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"get_data Execution Time: {execution_time} seconds")
    
    
    generate_startTime = time.time()
    coeff_path = audio_to_coeff.generate(batch, save_dir, pose_style, ref_pose_coeff_path)
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"audio_to_coeff.generate Execution Time: {execution_time} seconds")

    # 3dface render
    generate_startTime = time.time()
    if args.face3dvis:
        from src.face3d.visualize import gen_composed_video
        gen_composed_video(args, device, first_coeff_path, coeff_path, audio_path, os.path.join(save_dir, '3dface.mp4'))
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"gen_composed_video Execution Time: {execution_time} seconds")
    
    #coeff2video
    generate_startTime = time.time()
    data = get_facerender_data(coeff_path, crop_pic_path, first_coeff_path, audio_path, 
                                batch_size, input_yaw_list, input_pitch_list, input_roll_list,
                                expression_scale=args.expression_scale, still_mode=args.still, preprocess=args.preprocess, size=args.size)
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"get_facerender_data Execution Time: {execution_time} seconds")
    
    
    generate_startTime = time.time()
    result = animate_from_coeff.generate(data, save_dir, pic_path, crop_info, \
                                enhancer=args.enhancer, background_enhancer=args.background_enhancer, preprocess=args.preprocess, img_size=args.size)
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"animate_from_coeff.generate Execution Time: {execution_time} seconds")
    
    
    generate_startTime = time.time()
    shutil.move(result, save_dir+'.mp4')
    generate_endTime = time.time()    
    execution_time = generate_endTime - generate_startTime
    print(f"shutil.move Execution Time: {execution_time} seconds")
    
    print('The generated video is named:', save_dir+'.mp4')

    if not args.verbose:
        shutil.rmtree(save_dir)
        
    inference_endTime = time.time()
    
    execution_time = inference_endTime - inference_startTime
    print(f"Inference Execution Time: {execution_time} seconds")

    
if __name__ == '__main__':

    parser = ArgumentParser()  
    parser.add_argument("--driven_audio", default='./examples/driven_audio/bus_chinese.wav', help="path to driven audio")
    parser.add_argument("--source_image", default='./examples/source_image/full_body_1.png', help="path to source image")
    parser.add_argument("--ref_eyeblink", default=None, help="path to reference video providing eye blinking")
    parser.add_argument("--ref_pose", default=None, help="path to reference video providing pose")
    parser.add_argument("--checkpoint_dir", default='./checkpoints', help="path to output")
    parser.add_argument("--result_dir", default='./results', help="path to output")
    parser.add_argument("--pose_style", type=int, default=0,  help="input pose style from [0, 46)")
    parser.add_argument("--batch_size", type=int, default=2,  help="the batch size of facerender")
    parser.add_argument("--size", type=int, default=256,  help="the image size of the facerender")
    parser.add_argument("--expression_scale", type=float, default=1.,  help="the batch size of facerender")
    parser.add_argument('--input_yaw', nargs='+', type=int, default=None, help="the input yaw degree of the user ")
    parser.add_argument('--input_pitch', nargs='+', type=int, default=None, help="the input pitch degree of the user")
    parser.add_argument('--input_roll', nargs='+', type=int, default=None, help="the input roll degree of the user")
    parser.add_argument('--enhancer',  type=str, default=None, help="Face enhancer, [gfpgan, RestoreFormer]")
    parser.add_argument('--background_enhancer',  type=str, default=None, help="background enhancer, [realesrgan]")
    parser.add_argument("--cpu", dest="cpu", action="store_true") 
    parser.add_argument("--face3dvis", action="store_true", help="generate 3d face and 3d landmarks") 
    parser.add_argument("--still", action="store_true", help="can crop back to the original videos for the full body aniamtion") 
    parser.add_argument("--preprocess", default='crop', choices=['crop', 'extcrop', 'resize', 'full', 'extfull'], help="how to preprocess the images" ) 
    parser.add_argument("--verbose",action="store_true", help="saving the intermedia output or not" ) 
    parser.add_argument("--old_version",action="store_true", help="use the pth other than safetensor version" ) 


    # net structure and parameters
    parser.add_argument('--net_recon', type=str, default='resnet50', choices=['resnet18', 'resnet34', 'resnet50'], help='useless')
    parser.add_argument('--init_path', type=str, default=None, help='Useless')
    parser.add_argument('--use_last_fc',default=False, help='zero initialize the last fc')
    parser.add_argument('--bfm_folder', type=str, default='./checkpoints/BFM_Fitting/')
    parser.add_argument('--bfm_model', type=str, default='BFM_model_front.mat', help='bfm model')

    # default renderer parameters
    parser.add_argument('--focal', type=float, default=1015.)
    parser.add_argument('--center', type=float, default=112.)
    parser.add_argument('--camera_d', type=float, default=10.)
    parser.add_argument('--z_near', type=float, default=5.)
    parser.add_argument('--z_far', type=float, default=15.)

    args = parser.parse_args()

    if torch.cuda.is_available() and not args.cpu:
        args.device = "cuda"
    else:
        args.device = "cpu"

    main(args)

