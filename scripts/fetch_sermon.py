import sys
import os
import requests
from bs4 import BeautifulSoup
import re

def get_sermon(sermon_id):
    url = f"https://messagehub.info/en/readMessage.msg?ref_num={sermon_id}"
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, features="html.parser")

    # Extract title and place
    title_tag = soup.title
    date_code = title_tag.string.split()[0]
    title = title_tag.string[len(date_code):].strip()

    # Find title and place in the body
    body = soup.body
    sermon_title, sermon_place = None, None
    for div in body.find_all('div', class_='message-header'):
        sermon_title = div.find('h1').text
        sermon_place = div.find('h2').text

    # Extract paragraphs, preserving line breaks and document order
    # Include all content types: wmb, scripture, stanza, singing, heading
    paragraphs = []
    content_classes = ['wmb', 'scripture', 'stanza', 'singing', 'heading']
    for div in body.find_all('div'):
        if any(div.get('class') and class_name in div.get('class') for class_name in content_classes):
            # Use get_text('\n') to preserve line breaks within the div
            para_text = div.get_text('\n').strip('\n')
            if para_text:
                paragraphs.append(para_text)

    return sermon_title, sermon_place, paragraphs

def save_sermon_txt(sermon_id, title, place, paragraphs):
    output_dir = "input/en"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{sermon_id}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"{title}\n")
        f.write(f"{place}\n")
        for para in paragraphs:
            # Merge leading number and text if separated by a line break
            fixed_para = re.sub(r"^(\d+)\s*\n\s*", r"\1 ", para, count=1)
            f.write(f"{fixed_para}\n")
    print(f"Saved to {filename}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fetch_sermon.py <SERMON_ID>")
        sys.exit(1)
    sermon_id = sys.argv[1]
    title, place, paragraphs = get_sermon(sermon_id)
    save_sermon_txt(sermon_id, title, place, paragraphs)