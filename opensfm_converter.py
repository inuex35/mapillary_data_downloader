import cv2 
import perspective_and_equirectangular.lib.Equirec2Perspec as E2P
import perspective_and_equirectangular.lib.Perspec2Equirec as P2E
import perspective_and_equirectangular.lib.multi_Perspec2Equirec as m_P2E
import argparse
import numpy as np
from PIL import Image

def panorama2cube_image(pil_img):

    numpy_image = np.array(pil_img)
    height, width = numpy_image.shape[:2]
    cube_size = int(width / 4)

    opencv_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

    equ = E2P.Equirectangular(opencv_image)    # Load equirectangular image

    img_0 = equ.GetPerspective(90, 0, 0, cube_size, cube_size)  # Specify parameters(FOV, theta, phi, height, width)
    img_right = equ.GetPerspective(90, 90, 0, cube_size, cube_size)  # Specify parameters(FOV, theta, phi, height, width)
    img_left = equ.GetPerspective(90, -90, 0, cube_size, cube_size)  # Specify parameters(FOV, theta, phi, height, width)
    img_back = equ.GetPerspective(90, 180, 0, cube_size, cube_size)  # Specify parameters(FOV, theta, phi, height, width)

    img = cv2.hconcat([img_left, img_0, img_right, img_back])
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img)
    return pil_img

def main():
    parser = argparse.ArgumentParser(description="Convert equirectangular panorama to cube map.")
    parser.add_argument("input_image", type=str, help="Input equirectangular image.")
    args = parser.parse_args()
    panorama2cube_image(args.input_image)

if __name__ == "__main__":
    main()