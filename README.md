# EasyChat

This project is a PyQt5 application that allows users to **practice**, **take notes**, and **convert speech to text**. The application consists of three main components:

1. **Notes**: Allows users to take and edit text notes.
2. **Translator**: Enables users to translate text between different languages.
3. **Speech-to-Text**: Converts what the other person says into text in real-time.

## Features

- **Notes**: Easily take and organize notes. You can save and view any text you input.
- **Translation**: Translate text between two languages. Translate text written in one language to another.
- **Speech Recognition**: Convert spoken words into text using the microphone in real-time.

## Usage

### Requirements

- Python 3.x
- PyQt5
- Googletrans (or another translation library)
- SpeechRecognition (for speech-to-text functionality)

To install the required libraries, run the following command:

```bash
git clone https://github.com/MRamazan/EasyChat
cd EasyChat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 interface.py


