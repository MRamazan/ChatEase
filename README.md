# 🔵ChatEase

This project is a PyQt5 application that allows users to **practice**, **take notes**, and **convert speech to text**. The application consists of three main components:

1. **Notes**: Allows users to take notes, **(I am taking notes of the questions i will use for speaking practice.)**
2. **Translator**: Enables users to translate text between different languages.
3. **Speech-to-Text**: Converts what the other person says into **text**

## 🔵Features

- **Notes**: Take notes **(automatic romaji for Japanese notes)**
  
- **Translation**: Translate text between two languages. **(It uses Helsinki-NLP for EN-JA JA-EN translate, google translate for other langauges)**
  
- **Speech Recognition**: Convert spoken words into text.

## 🔵Setup

### 🔵Requirements
- Python 3.x
  
- PyTorch (https://pytorch.org/get-started/locally/)



```bash
git clone https://github.com/MRamazan/ChatEase
cd EasyChat

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 interface.py
