import requests
from io import BytesIO
import os, sys, zlib
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image
import json
import configparser
import base64

sequence_entries = []

def save_token_to_ini(access_token, file_path='token.ini'):
    config = configparser.ConfigParser()
    config['DEFAULT'] = {'Access_Token': access_token}
    with open(file_path, 'w') as configfile:
        config.write(configfile)

def read_token_from_ini(file_path='token.ini'):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config['DEFAULT'].get('Access_Token', None)

def download_function(access_token, sequence_id, progress_var, sequence_num):
    save_token_to_ini(access_token)
    header = {'Authorization': 'OAuth {}'.format(access_token)}
    try:
        sequence_url = "https://graph.mapillary.com/image_ids?sequence_id={}".format(sequence_id)
        sequence_response = requests.get(sequence_url, headers=header)
        sequence_response.raise_for_status()
        sequence_response_json = sequence_response.json()
        total_images = len(sequence_response_json["data"])  # 画像の総数を取得
        image_dir = os.path.join(sequence_id, 'images')
        distoted_image_dir = os.path.join(sequence_id, 'images_distorted')
        for index, img_id in enumerate(sequence_response_json["data"]):
            image_info_url = 'https://graph.mapillary.com/{}?fields=thumb_original_url, captured_at, is_pano'.format(img_id["id"])
            img_response = requests.get(image_info_url, headers=header)
            img_response.raise_for_status()
            img_response_json = img_response.json()
            image_name = int(img_response_json["captured_at"])
            image_get_url = img_response_json['thumb_original_url']
            image_bytes = requests.get(image_get_url, stream=True).content
            image = Image.open(BytesIO(image_bytes))
            if img_response_json["is_pano"]:
                if not os.path.exists(image_dir):
                    os.makedirs(image_dir)
                image.save(os.path.join(image_dir, '{}.jpg'.format(image_name)))
            else:
                if not os.path.exists(distoted_image_dir):
                    os.makedirs(distoted_image_dir)
                image.save(os.path.join(distoted_image_dir, '{}.jpg'.format(image_name)))
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
        sfm_data_json = json.loads(sfm_data.decode('utf-8'))  # zlibから解凍したバイナリデータを文字列に変換し、JSONにパースする
        temp_shots = {}
        for _, shot_data in sfm_data_json[0]['shots'].items():
            new_shot_id = str(int(shot_data["capture_time"] * 1000)) + ".jpg"
            temp_shots[new_shot_id] = shot_data
        sfm_data_json[0]['shots'] = temp_shots
        sfm_data_to_write = json.dumps(sfm_data_json, indent=2, ensure_ascii=False)  # JSONデータを整形する
        if img_response_json["is_pano"]:
            with open(os.path.join(sequence_id, "reconstruction.json"), 'w') as sfm_file:
                sfm_file.write(sfm_data_to_write)
        else:
            with open(os.path.join(sequence_id, "reconstruction_distorted.json"), 'w') as sfm_file:
                sfm_file.write(sfm_data_to_write)
    except requests.exceptions.RequestException as e:
        print(f"Error downloading the image: {e}")

def add_entry_field():
    new_entry = tk.Entry(root)
    new_entry.pack()
    sequence_entries.append(new_entry)

def on_download_clicked():
    access_token = entry_token.get()
    for sequence_num, sequence_id in enumerate(sequence_entries):
        sequence_id = sequence_id.get().strip()
        if sequence_id:
            download_function(access_token, sequence_id, progress_var, sequence_num + 1)
    messagebox.showinfo("Download Complete", "File download completed.")

# GUI setup
root = tk.Tk()
root.geometry('200x400')  # ウィンドウのサイズを調整
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
    # 新しいエントリーフィールドを追加
    new_entry = tk.Entry(sequence_container)
    new_entry.pack()  # pack を使うとデフォルトで下に追加される
    sequence_entries.append(new_entry)
    # スクロールバーの範囲を更新
    scrollable_sequence_canvas.configure(scrollregion=scrollable_sequence_canvas.bbox("all"))
    # スクロールして新しいエントリーが見えるようにする
    scrollable_sequence_canvas.yview_moveto(1.0)

button_add.config(command=add_entry_field)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(button_frame, orient="horizontal", length=200, mode="determinate", variable=progress_var)
progress_bar.pack(side="bottom")

progress_label = tk.Label(button_frame, text="0/0 (0%)")
progress_label.pack(side="bottom")

root.mainloop()