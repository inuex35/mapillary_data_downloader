import requests
from io import BytesIO
import os, sys, zlib
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image
import json
import configparser
import piexif
import base64, mapbox_vector_tile
import numpy as np
import random
import cv2 
from dictknife import deepmerge
from queue import Queue
import shutil
from equilib import Equi2Pers

sequence_entries = []
is_cancelled = False
update_queue = Queue()

def add_gps_info_to_image_data(latitude, longitude):
    def convert_to_degrees(value):
        d = int(value)
        m = int((value - d) * 60)
        s = (value - d - m/60) * 3600
        return d, m, s

    lat_deg = convert_to_degrees(latitude)
    lon_deg = convert_to_degrees(longitude)

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if latitude >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: [(lat_deg[0], 1), (lat_deg[1], 1), (int(lat_deg[2]*100), 100)],
        piexif.GPSIFD.GPSLongitudeRef: 'E' if longitude >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: [(lon_deg[0], 1), (lon_deg[1], 1), (int(lon_deg[2]*100), 100)],
    }

    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    return exif_bytes

def save_token_to_ini(access_token, file_path='token.ini'):
    config = configparser.ConfigParser()
    config['DEFAULT'] = {'Access_Token': access_token}
    with open(file_path, 'w') as configfile:
        config.write(configfile)

def read_token_from_ini(file_path='token.ini'):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config['DEFAULT'].get('Access_Token', None)

# マージと画像ファイルの移動を行う関数
def merge_and_move_files(sequence_ids):
    merged_data = []
    merged_data_dir = "merged"
    merged_image_dir = "merged/images"
    if not os.path.exists(merged_data_dir):
        os.makedirs(merged_data_dir)
    if not os.path.exists(merged_image_dir):
        os.makedirs(merged_image_dir)

    # JSONファイルのマージ
    for sequence_id in sequence_ids:
        file_path = os.path.join(sequence_id, "reconstruction.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data = json.load(file)
                merged_data = merged_data + data
                os.remove(file_path)
    for sequence_id in sequence_ids:
        image_dir = os.path.join(sequence_id, 'images')
        if os.path.exists(image_dir):
            for image_file in os.listdir(image_dir):
                src_path = os.path.join(image_dir, image_file)
                dst_path = os.path.join(merged_image_dir, image_file)
                if os.path.exists(dst_path):  
                    os.remove(dst_path)
                shutil.move(src_path, dst_path)
        shutil.rmtree(sequence_id)

    # マージされた JSON データを保存
    with open('merged/reconstruction.json', 'w') as file:
        json.dump(merged_data, file, indent=2)

def equi2perspective(image, rots, height, width):
    equi2pers = Equi2Pers(height=height, width=width, fov_x=90.0, mode="bilinear")
    perspective_image = equi2pers(equi=image,rots=rots)
    perspective_image = np.transpose(perspective_image, (1, 2, 0))
    return perspective_image

def download_function(access_token, sequence_id, progress_var, sequence_num, download_mask, should_merge):
    save_token_to_ini(access_token)
    header = {'Authorization': 'OAuth {}'.format(access_token)}
    try:
        sequence_url = "https://graph.mapillary.com/image_ids?sequence_id={}".format(sequence_id)
        sequence_response = requests.get(sequence_url, headers=header)
        sequence_response.raise_for_status()
        sequence_response_json = sequence_response.json()
        total_images = len(sequence_response_json["data"]) 
        image_dir = os.path.join(sequence_id, 'images')
        if not os.path.exists(sequence_id):
            os.makedirs(sequence_id)
        for index, img_id in enumerate(sequence_response_json["data"]):
            image_info_url = 'https://graph.mapillary.com/{}?fields=thumb_original_url, captured_at, is_pano, geometry, camera_parameters, camera_type'.format(img_id["id"])
            geometry_info_url = 'https://graph.mapillary.com/{}/detections?access_token={}&fields=geometry'.format(img_id["id"], access_token)
            img_response = requests.get(image_info_url, headers=header)
            geometry_response = requests.get(geometry_info_url, headers=header)
            img_response.raise_for_status()
            img_response_json = img_response.json()
            geometry_response_json = geometry_response.json()
            image_name = int(img_response_json["captured_at"])
            image_get_url = img_response_json['thumb_original_url']
            image_bytes = requests.get(image_get_url, stream=True).content
            exif_bytes = add_gps_info_to_image_data(img_response_json['geometry']['coordinates'][1], img_response_json['geometry']['coordinates'][0])
            image = Image.open(BytesIO(image_bytes))
            width, height = image.size
            if img_response_json["is_pano"]:
                if not os.path.exists(image_dir):
                    os.makedirs(image_dir)
                if should_merge:
                    if not os.path.exists(image_dir):
                        os.makedirs(image_dir)
                    image = np.asarray(image, dtype=np.uint8)
                    image = np.transpose(image, (2, 0, 1))
                    rots = {'roll': 0., 'pitch': 0, 'yaw': 0}
                    rots_r = {'roll': 0., 'pitch': 0, 'yaw': - np.pi/2}
                    rots_b = {'roll': 0., 'pitch': 0, 'yaw': np.pi}
                    rots_l = {'roll': 0., 'pitch': 0, 'yaw': np.pi/2}
                    perspective_image_f = equi2perspective(image,rots,int(width/4),int(width/4))
                    perspective_image_r = equi2perspective(image,rots_r,int(width/4),int(width/4))
                    perspective_image_b = equi2perspective(image,rots_b,int(width/4),int(width/4))
                    perspective_image_l = equi2perspective(image,rots_l,int(width/4),int(width/4))
                    perspective_image = cv2.hconcat([perspective_image_l, perspective_image_f, perspective_image_r, perspective_image_b])
                    perspective_image_pil = Image.fromarray(perspective_image)
                    perspective_image_pil.save(os.path.join(image_dir, '{}.jpg'.format(image_name)), exif=exif_bytes)
                else:
                    image_dir = os.path.join(sequence_id, 'images')
                    image.save(os.path.join(image_dir, '{}.jpg'.format(image_name)), exif=exif_bytes)
            else:
                if not os.path.exists(image_dir):
                    os.makedirs(image_dir)
                if should_merge:
                    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                    print(img_response_json['camera_parameters'])
                    cameraMatrix = np.array([img_response_json['camera_parameters'][0] * width, 0 , width/2, 0, img_response_json['camera_parameters'][0] * width, height/2, 0, 0, 1]).reshape(3,3)
                    distCoeff = np.array([img_response_json['camera_parameters'][1], img_response_json['camera_parameters'][2], 0, 0, 0])
                    h, w = image_cv.shape[:2]
                    newCameraMatrix, roi = cv2.getOptimalNewCameraMatrix(cameraMatrix, distCoeff, (w,h), 1, (w,h))
                    undistorted_image = cv2.undistort(image_cv, cameraMatrix, distCoeff, None, newCameraMatrix)
                    undistorted_image_pil = Image.fromarray(cv2.cvtColor(undistorted_image, cv2.COLOR_BGR2RGB))
                    undistorted_image_pil.save(os.path.join(image_dir, '{}.jpg'.format(image_name)), exif=exif_bytes)
                else:
                    image.save(os.path.join(image_dir, '{}.jpg'.format(image_name)), exif=exif_bytes)
            if download_mask:
                mask = np.zeros((height, width, 3), dtype=np.uint8)
                mask_dir = os.path.join(sequence_id, 'mask')
                if not os.path.exists(mask_dir):
                    os.makedirs(mask_dir)
                for geometry in geometry_response_json['data']:
                    base64_string = geometry['geometry']
                    vector_data = base64.decodebytes(base64_string.encode('utf-8'))
                    decoded_geometry = mapbox_vector_tile.decode(vector_data)
                    detection_coordinates = decoded_geometry['mpy-or']['features'][0]['geometry']['coordinates'][0]
                    pixel_coords = np.array([[int(x/4096 * height), int(y/4096 * width)] for x, y in detection_coordinates])
                    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                    cv2.fillPoly(mask, [pixel_coords], color)
                cv2.imwrite(os.path.join(mask_dir, '{}.jpg'.format(image_name)), mask)
            current_progress = (index + 1) / total_images * 100
            progress_label.config(text=f"sec {sequence_num}: {index + 1}/{total_images} ({current_progress:.2f}%)")
            progress_var.set((index + 1) / total_images * 100)
            root.update_idletasks()
        image_url = 'https://graph.mapillary.com/{}?fields=thumb_original_url, sfm_cluster'.format(img_id["id"])
        response = requests.get(image_url, headers=header)
        response.raise_for_status()
        response_json = response.json()
        sfm_cluster_url = response_json["sfm_cluster"]["url"]
        sfm_data_zlib = requests.get(sfm_cluster_url, stream=True).content
        sfm_data = zlib.decompress(sfm_data_zlib)
        sfm_data_json = json.loads(sfm_data.decode('utf-8'))
        temp_shots = {}
        for shot_id, shot_data in sfm_data_json[0]['shots'].items():
            #new_shot_id = str(int(shot_data["capture_time"] * 1000)) + ".jpg"
            new_shot_id = shot_id + ".jpg"
            org_image_name = str(int(shot_data["capture_time"] * 1000)) + ".jpg"
            shutil.move(os.path.join(image_dir, org_image_name), os.path.join(image_dir, new_shot_id))
            temp_shots[new_shot_id] = shot_data
        sfm_data_json[0]['shots'] = temp_shots
        sfm_data_to_write = json.dumps(sfm_data_json, indent=2, ensure_ascii=False)  # JSONデータを整形する
        if img_response_json["is_pano"]:
            with open(os.path.join(sequence_id, "reconstruction.json"), 'w') as sfm_file:
                sfm_file.write(sfm_data_to_write)
        else:
            with open(os.path.join(sequence_id, "reconstruction.json"), 'w') as sfm_file:
                sfm_file.write(sfm_data_to_write)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading the image: {e}")

def add_entry_field():
    new_entry = tk.Entry(root)
    new_entry.pack()
    sequence_entries.append(new_entry)

def on_download_clicked():
    access_token = entry_token.get()
    download_mask = mask_var.get() == 1
    should_merge = merge_var.get() == 1  # マージを行うかどうか

    sequence_ids = [entry.get().strip() for entry in sequence_entries if entry.get().strip()]
    for sequence_num, sequence_id in enumerate(sequence_ids):
        if sequence_id:
            download_function(access_token, sequence_id, progress_var, sequence_num + 1, download_mask, should_merge)
    
    if should_merge and sequence_ids:
        merge_and_move_files(sequence_ids)
        messagebox.showinfo("Merge Complete", "Reconstruction files merged and images moved.")
    else:
        messagebox.showinfo("Download Complete", "File download completed.")

# GUI setup
root = tk.Tk()
root.geometry('200x500')
root.title("Download Tool")

label_token = tk.Label(root, text="Access Token(start from MLY):")
label_token.pack()

entry_token = tk.Entry(root)
entry_token.pack()

token_from_ini = read_token_from_ini()
if token_from_ini:
    entry_token.insert(0, token_from_ini)
sequence_frame = tk.Frame(root)
sequence_frame.pack(fill="both", expand=True)

scrollbar = ttk.Scrollbar(sequence_frame, orient="vertical")
scrollable_sequence_canvas = tk.Canvas(sequence_frame, yscrollcommand=scrollbar.set)
scrollbar.config(command=scrollable_sequence_canvas.yview)
scrollbar.pack(side="right", fill="y")
scrollable_sequence_canvas.pack(side="left", fill="both", expand=True)

sequence_container = ttk.Frame(scrollable_sequence_canvas)
scrollable_sequence_canvas.create_window((0, 0), window=sequence_container, anchor="nw")
sequence_container.bind("<Configure>", lambda e: scrollable_sequence_canvas.configure(scrollregion=scrollable_sequence_canvas.bbox("all")))

label_id = tk.Label(sequence_container, text="Sequence ID:")
label_id.pack()

entry_id = tk.Entry(sequence_container)
entry_id.pack()
sequence_entries.append(entry_id)

button_frame = tk.Frame(root)
button_frame.pack(fill='x', side='bottom')

button_add = tk.Button(button_frame, text="ADD", command=add_entry_field)
button_add.pack(side='top', fill='x', expand=True)

button_download = tk.Button(button_frame, text="Download", command=on_download_clicked)
button_download.pack(side='top', fill='x', expand=True)

def add_entry_field():
    new_entry = tk.Entry(sequence_container)
    new_entry.pack() 
    sequence_entries.append(new_entry)
    scrollable_sequence_canvas.configure(scrollregion=scrollable_sequence_canvas.bbox("all"))
    scrollable_sequence_canvas.yview_moveto(1.0)

button_add.config(command=add_entry_field)
mask_var = tk.IntVar()

checkbutton_mask = tk.Checkbutton(root, text="Download Mask", variable=mask_var)
checkbutton_mask.pack()

# マージするかどうかを制御するチェックボックスと変数
merge_var = tk.IntVar()
checkbutton_merge = tk.Checkbutton(root, text="Merge Files", variable=merge_var)
checkbutton_merge.pack()


progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(button_frame, orient="horizontal", length=200, mode="determinate", variable=progress_var)
progress_bar.pack(side="bottom")

progress_label = tk.Label(button_frame, text="0/0 (0%)")
progress_label.pack(side="bottom")

root.mainloop()
