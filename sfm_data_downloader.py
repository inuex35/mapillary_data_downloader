import requests
from io import BytesIO
import os, sys, zlib
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image
import json
import configparser
import base64

def save_token_to_ini(access_token, file_path='token.ini'):
    config = configparser.ConfigParser()
    config['DEFAULT'] = {'Access_Token': access_token}
    with open(file_path, 'w') as configfile:
        config.write(configfile)

def read_token_from_ini(file_path='token.ini'):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config['DEFAULT'].get('Access_Token', None)

def download_function(access_token, sequence_id, progress_var):
    save_token_to_ini(access_token)
    header = {'Authorization': 'OAuth {}'.format(access_token)}
    try:
        sequence_url = "https://graph.mapillary.com/image_ids?sequence_id={}".format(sequence_id)
        sequence_response = requests.get(sequence_url, headers=header)
        sequence_response.raise_for_status()
        sequence_response_json = sequence_response.json()
        total_images = len(sequence_response_json["data"])  # 画像の総数を取得
        image_dir = os.path.join(sequence_id, 'images')
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
        for index, img_id in enumerate(sequence_response_json["data"]):
            image_info_url = 'https://graph.mapillary.com/{}?fields=thumb_original_url'.format(img_id["id"])
            img_response = requests.get(image_info_url, headers=header)
            img_response.raise_for_status()
            img_response_json = img_response.json()
            image_get_url = img_response_json['thumb_original_url']
            image_bytes = requests.get(image_get_url, stream=True).content
            image = Image.open(BytesIO(image_bytes))
            image.save(os.path.join(image_dir, '{}.jpg'.format(img_id["id"])))
            current_progress = (index + 1) / total_images * 100
            progress_label.config(text=f"{index + 1}/{total_images} ({current_progress:.2f}%)")
            progress_var.set((index + 1) / total_images * 100)
            root.update_idletasks()
        image_url = 'https://graph.mapillary.com/{}?fields=thumb_original_url, sfm_cluster, captured_at'.format(img_id["id"])
        response = requests.get(image_url, headers=header)
        response.raise_for_status()
        response_json = response.json()
        captured_at = response_json["captured_at"]
        sfm_cluster_url = response_json["sfm_cluster"]["url"]
        sfm_data_zlib = requests.get(sfm_cluster_url, stream=True).content
        sfm_data = zlib.decompress(sfm_data_zlib)
        sfm_data_json = json.loads(sfm_data.decode('utf-8'))  # zlibから解凍したバイナリデータを文字列に変換し、JSONにパースする
        sfm_data_to_write = json.dumps(sfm_data_json, indent=2, ensure_ascii=False)  # JSONデータを整形する
        with open(os.path.join(sequence_id, "reconstruction.json"), 'w') as sfm_file:
            sfm_file.write(sfm_data_to_write)
        messagebox.showinfo("Download Complete", "File download completed.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading the image: {e}")

def on_download_clicked():
    access_token = entry_token.get()
    id = entry_id.get()
    progress_var.set(0)
    download_function(access_token, id, progress_var)

# GUI setup
root = tk.Tk()
root.title("Download Tool")

label_token = tk.Label(root, text="Access Token(start from MLY):")
label_token.pack()

entry_token = tk.Entry(root)
entry_token.pack()

token_from_ini = read_token_from_ini()
if token_from_ini:
    entry_token.insert(0, token_from_ini)

label_id = tk.Label(root, text="Sequence ID:")
label_id.pack()

entry_id = tk.Entry(root)
entry_id.pack()

button_download = tk.Button(root, text="Download", command=on_download_clicked)
button_download.pack()

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(root, orient="horizontal", length=200, mode="determinate", variable=progress_var)
progress_bar.pack()

progress_label = tk.Label(root, text="0/0 (0%)")
progress_label.pack()

root.mainloop()