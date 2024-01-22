# Mapillary Data Downloader

When you open the app, you will see the following GUI:

1. Input the access token.
2. Enter the sequence ID in the sequence input field.
3. Use the 'add' button to add more sequence input fields.
4. Start the download by clicking the 'Download' button.
5. Press the 'merge' button to combine the data into a single folder named 'merged'.

When the merge option is used, images from equirectangular projections have their top and bottom removed and are processed into horizontally concatenated cube images. For perspective images, the distortions are removed to create processed images. These images can be directly used for 360 Gaussian splatting.

![Mapillary Data Downloader GUI](https://github.com/inuex35/mapillary_data_downloader/assets/129066540/533c6def-9fbe-4c43-bae7-f8286dc40379)
