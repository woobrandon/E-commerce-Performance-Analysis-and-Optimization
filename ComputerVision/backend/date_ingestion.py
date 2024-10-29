from tensorflow.keras.applications import ResNet50
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input
from scipy.spatial.distance import cosine
from bs4 import BeautifulSoup
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import pandas as pd
import sqlite3
import time
import os
import requests

# initialise the model using the weights obtained from training
model = ResNet50(weights='resnet50_weights_tf_dim_ordering_tf_kernels_notop.h5',
                 include_top=False, pooling='avg')

amazon_df = pd.read_csv("../amazon.csv")


def extract_features(img_path):
    """
    Extract the features from each image
    """
    img = image.load_img(img_path, target_size=(224, 224))
    x = image.img_to_array(img)
    x = preprocess_input(x)
    features = model.predict(x[None, ...])
    return features


def create_table():
    """
    Create a table with the columns id, filename, features and productUrl
    """
    # Connect to the SQLite database
    conn = sqlite3.connect('feature_database.db')
    cursor = conn.cursor()

    # Drop the table if it exists
    cursor.execute('DROP TABLE IF EXISTS features')

    # Create the table with the correct schema
    cursor.execute('''
    CREATE TABLE features (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        features BLOB,
        productUrl TEXT,
        about TEXT
    )
    ''')
    conn.commit()
    conn.close()
    print("Table initialized!")

def insert_features(id, filename, features, productUrl, about):
    """
    Inserts features into database after extracting it with the extract function
    """
    conn = sqlite3.connect('feature_database.db')
    cursor = conn.cursor()

    # Convert features to binary format
    features_blob = features.tobytes()

    cursor.execute('''
    INSERT INTO features (id, filename, features, productUrl, about) VALUES (?, ?, ?, ?, ?)
    ''', (id, filename, features_blob, productUrl, about))

    conn.commit()
    conn.close()
    return

def scrape_amzn_images():
    """
    Downloads the images from the amazon csv file either through the image url or scraping the amazon website
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    images = amazon_df[["img_link", "product_link"]]
    n = len(images)
    service = Service('./chromedriver')
    driver = webdriver.Chrome(service=service)

    for i in range(i, n+1):
        response = requests.get(images.iloc[i-1]["img_link"])
        if response.status_code == 200:
            with open("../amazon_images/image_" + str(i) + ".jpg", "wb") as file:
                file.write(response.content)
        else:
            response = requests.get(images.iloc[i-1]["product_link"])
            product_link = images.iloc[i-1]["product_link"]
            driver.get(product_link)
            time.sleep(1.5)
            try:
                image_tag = driver.find_element(By.ID, 'landingImage')
                soup = BeautifulSoup(response.content, 'html.parser')
                image_url = image_tag.get_attribute('src')

                if image_url:
                    img_response = requests.get(image_url)
                    img_response.raise_for_status()
                    with open("../amazon_images/image_" + str(i) + ".jpg", "wb") as file:
                        file.write(img_response.content)
            except Exception as e:
                print("file number" + str(i) + "did not print")
    print("Scraping complete!")
    return


create_table()

folder_path = '../amazon_images'

# Scrapes the amazon website
# if not os.path.exists(folder_path):
#     os.makedirs(folder_path)
#     scrape_amzn_images()
# else:
#     scrape_amzn_images()

db_id = 0

for img in os.listdir(folder_path):
    try:
        img_path = os.path.join(folder_path, img)
        img_features = extract_features(img_path)
        insert_features(db_id, img, img_features, amazon_df["product_link"][int(img[6:-4])-1], amazon_df["about_product"][int(img[6:-4])-1])
        db_id += 1
    except:
        print(str(img) + " was unable to be inserted")

