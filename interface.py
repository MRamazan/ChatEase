
import sys

import torch
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QLineEdit, QPushButton, QListWidget,
                           QListWidgetItem, QLabel, QMessageBox, QComboBox,
                           QTextEdit, QSplitter)
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QIcon
import json
import re
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QSizePolicy
import cutlet
from PyQt5.QtWidgets import (QComboBox, QCompleter)
from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QTimer
from deep_translator import GoogleTranslator
from langdetect import detect
from transformers import MarianTokenizer, MarianMTModel
import soundcard as sc
import soundfile as sf
import speech_recognition as sr
import numpy as np
from queue import Queue
from threading import Thread
import audioop
import whisper
from gtts import gTTS
import os
from pygame import mixer
import tempfile

helsinki_ja_en = "Helsinki-NLP/opus-mt-ja-en"
helsinki_en_ja = "Helsinki-NLP/opus-tatoeba-en-ja"


process_clicked = None


class SearchableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(10)

        self.model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.completer = QCompleter(self.proxy_model, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)

        self.setStyleSheet("""
            QComboBox {
                padding: 8px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                min-width: 200px;
                font-size: 14px;
            }

            QComboBox:hover {
                border-color: #2196F3;
            }

            QComboBox:focus {
                border-color: #1976D2;
                outline: none;
            }

            QComboBox::drop-down {
                width: 30px;
                border: none;
                background: transparent;
            }

            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                margin-right: 15px;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM0NDQ0NDQiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=);
            }

            QComboBox QAbstractItemView {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: transparent;
                outline: none;
                padding: 5px;
                margin-top: 5px;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px 15px;
                min-height: 25px;
                border-radius: 4px;
                margin: 2px 4px;
                color: #333333;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #E3F2FD;
                color: #1976D2;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #BBDEFB;
                color: #1565C0;
            }

            QComboBox QScrollBar:vertical {
                width: 8px;
                background: #F5F5F5;
                border-radius: 4px;
                margin: 0px;
            }

            QComboBox QScrollBar::handle:vertical {
                background: #BDBDBD;
                border-radius: 4px;
                min-height: 30px;
            }

            QComboBox QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }

            QComboBox QScrollBar::add-line:vertical,
            QComboBox QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QComboBox QScrollBar::add-page:vertical,
            QComboBox QScrollBar::sub-page:vertical {
                background: none;
            }

            QListView::item {
                padding: 8px 15px;
            }
        """)

        self.lineEdit().textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text):
        self.proxy_model.setFilterFixedString(text)

    def addItems(self, items):
        for text in items:
            item = QStandardItem(text)
            self.model.appendRow(item)

    def currentText(self):
        return self.lineEdit().text()


class TTSThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, text, lang='en'):
        super().__init__()
        self.text = text
        self.lang = lang
        mixer.init()

    def run(self):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                temp_filename = fp.name

            tts = gTTS(text=self.text, lang=self.lang)
            tts.save(temp_filename)


            mixer.music.load(temp_filename)
            mixer.music.play()

            while mixer.music.get_busy():
                continue

            os.unlink(temp_filename)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()


from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject


class WorkerSignals(QObject):
    finished = pyqtSignal(str, bool)

class TranslationWorker(QRunnable):
    def __init__(self, text, source_lang, target_lang, model):
        super().__init__()
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.model = model[0]
        self.tokenizer = model[1]

        self.signals = WorkerSignals()


    @pyqtSlot()
    def run(self):
        try:
            inputs = self.tokenizer(self.text, return_tensors="pt", padding=True, truncation=True)
            translated = self.model.generate(**inputs.to("cuda"))
            translated_text = self.tokenizer.decode(translated[0], skip_special_tokens=True)
        except Exception:
            try:
                translated_text = GoogleTranslator(source=self.source_lang, target=self.target_lang).translate(self.text)
            except Exception as e:
                self.signals.finished.emit(f"Translate error: {str(e)}", False)
                return

        if self.target_lang == "ja":
            import cutlet
            cutlet_romaji = cutlet.Cutlet().romaji(translated_text)
            formatted_text = f"{translated_text}<br><span style='color: #666; font-size: 18px; font-style: italic;'>{cutlet_romaji}</span>"
            self.signals.finished.emit(formatted_text, True)
        else:
            self.signals.finished.emit(translated_text, False)





class SpeechRecognitionThread(QThread):
    textRecognized = pyqtSignal(str, str, bool)

    def __init__(self):
        super().__init__()
        self.SAMPLE_RATE = 48000
        self.CHUNK_SIZE = 1024
        self.SILENCE_THRESHOLD = 1000
        self.SILENCE_CHUNKS = 20
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model("tiny").to(device)
        self.audio_queue = Queue()
        self.is_recording = True
        self.speaker_colors = {}

    def get_speaker_color(self, speaker_id):
        if speaker_id not in self.speaker_colors:
            colors = ['#FF4444', '#44FF44', '#4444FF', '#FFFF44', '#FF44FF', '#44FFFF']
            self.speaker_colors[speaker_id] = colors[5]
        return self.speaker_colors[speaker_id]

    def record_audio(self):
        global process_clicked
        with sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True).recorder(
                samplerate=self.SAMPLE_RATE) as mic:
            current_chunk = []
            silence_counter = 0

            while self.is_recording:
                chunk = mic.record(numframes=self.CHUNK_SIZE)
                chunk = chunk[:, 0]

                if process_clicked:
                    rms = 0
                else:
                    rms = audioop.rms(chunk.tobytes(), 2)

                if rms < self.SILENCE_THRESHOLD:
                    silence_counter += 1
                else:
                    silence_counter = 0

                current_chunk.extend(chunk)

                if process_clicked:
                 if silence_counter >= 150:
                    if len(current_chunk) > 0:
                        self.audio_queue.put(np.array(current_chunk))
                    current_chunk = []
                    silence_counter = 0
                else:
                     if silence_counter >= self.SILENCE_CHUNKS:
                         if len(current_chunk) > 0:
                             self.audio_queue.put(np.array(current_chunk))
                         current_chunk = []
                         silence_counter = 0



    def process_audio(self):
        global process_clicked
        while self.is_recording or not self.audio_queue.empty():
            if not self.audio_queue.empty():
                audio_chunk = self.audio_queue.get()

                temp_filename = "temp.wav"
                sf.write(temp_filename, audio_chunk, self.SAMPLE_RATE)

                result = self.model.transcribe(temp_filename)
                print(result["segments"])

                segments = []
                for segment in result["segments"]:
                    text = segment["text"]
                    id = segment["id"]


                    segments.append({
                        "start": "00:00",
                        "end": "00:00",
                        "speaker": str(id),
                        "text": text
                    })

                for i, segment in enumerate(sorted(segments, key=lambda x: x["start"])):
                    if segment["text"].strip():
                        if i == len(segments) - 1:
                            self.textRecognized.emit(segment["text"], segment["speaker"], True)
                        else:
                            self.textRecognized.emit(segment["text"], segment["speaker"], False)

                process_clicked = False

    def run(self):
        record_thread = Thread(target=self.record_audio)
        process_thread = Thread(target=self.process_audio)

        record_thread.start()
        process_thread.start()

        record_thread.join()
        process_thread.join()

    def stop(self):
        self.is_recording = False


class Speech2TextWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.recognition_thread = None
        self.speaker_colors = {}
        self.katsu = cutlet.Cutlet()

    def setup_ui(self):
        layout = QVBoxLayout()


        self.label = QLabel("Speech To Text")
        self.label.setStyleSheet("""
            font-size: 30px;
            font-weight: bold;
            margin-bottom: 15px;
        """)


        self.label.setAlignment(Qt.AlignCenter)

        self.text_area = QTextEdit()
        self.text_area.setStyleSheet("""
            font-size: 18px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background-color: white;
        """)

        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Recognized text will appear here...")



        button_layout = QHBoxLayout()

        self.start_button = QPushButton("Start Recording")
        self.stop_button = QPushButton("Stop Recording")
        self.clear_button = QPushButton("Clear Text")
        self.process_button = QPushButton("Process")


        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)


        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)


        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)


        self.stop_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.process_button)


        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.clear_button.clicked.connect(self.clear_text)
        self.process_button.clicked.connect(self.force_process_audio)



        layout.addWidget(self.label)
        layout.addWidget(self.text_area)
        layout.addLayout(button_layout)


        self.setLayout(layout)


    def force_process_audio(self):
        global process_clicked
        process_clicked = True


    def start_recording(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.recognition_thread = SpeechRecognitionThread()
        self.recognition_thread.textRecognized.connect(self.update_text)
        self.recognition_thread.start()


    def stop_recording(self):
        if self.recognition_thread:
            self.recognition_thread.stop()
            self.recognition_thread.wait()
            self.recognition_thread = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)


    def is_japanese(self, text):
        return bool(re.search("[\u3040-\u30FF\u4E00-\u9FFF]", text))


    def to_romaji(self, text):
        return self.katsu.romaji(text)


    def update_text(self, text, sentence_id, last):
        colors = ['#FF4444', '#44FF44', '#4444FF', '#FFFF44', '#FF44FF', '#44FFFF']
        if sentence_id not in self.speaker_colors:
            self.speaker_colors[sentence_id] = colors[len(self.speaker_colors) % len(colors)]

        color = self.speaker_colors[sentence_id]

        romaji_text = self.to_romaji(text) if self.is_japanese(text) else ""


        formatted_text = f'<div style="margin-bottom: 10px;">'
        formatted_text += f'<span style="color: {color}; font-weight: bold;">{sentence_id}: </span>'
        formatted_text += f'<span>{text}</span>'

        if romaji_text:
            formatted_text += f'<br><span style="font-style: italic; color: gray;">{romaji_text}</span>'

        if last:
            formatted_text += '<br><br><span>|-----------------------------------------------------------------------|</span>'

        formatted_text += '</div><br>'

        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        self.text_area.setTextCursor(cursor)
        self.text_area.insertHtml(formatted_text)



    def clear_text(self):
        self.text_area.clear()
        self.speaker_colors.clear()


    def closeEvent(self, event):
        if self.recognition_thread:
            self.stop_recording()
        event.accept()


class TodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatEase")
        self.setMinimumSize(1700, 800)
        self.katsu = cutlet.Cutlet()
        self.katsu.use_foreign_spelling = False


        self.light_style = """
            QMainWindow {
                background-color: #f0f2f5;
            }
            QLineEdit, QTextEdit {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                font-size: 14px;
                background-color: white;
            }
            QPushButton {
                padding: 10px 20px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QListWidget {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }

            
            QListWidget::item {
        padding: 10px;
        margin: 2px 0;
        border-radius: 3px;
        background-color: #f8f9fa;
    }
    QListWidget::item:selected {
        background-color: #e3f2fd;
        color: #1976d2;
    }
    QScrollBar:vertical {
        border: none;
        background: #f0f0f0;
        width: 12px;
        margin: 0px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #c0c0c0;
        min-height: 30px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical:hover {
        background: #a0a0a0;
    }
    QScrollBar::add-line:vertical {
        border: none;
        background: none;
        height: 0px;
    }
    QScrollBar::sub-line:vertical {
        border: none;
        background: none;
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
    QScrollBar:horizontal {
        border: none;
        background: #f0f0f0;
        height: 12px;
        margin: 0px;
        border-radius: 6px;
    }
    QScrollBar::handle:horizontal {
        background: #c0c0c0;
        min-width: 30px;
        border-radius: 6px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #a0a0a0;
    }
    QScrollBar::add-line:horizontal {
        border: none;
        background: none;
        width: 0px;
    }
    QScrollBar::sub-line:horizontal {
        border: none;
        background: none;
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;}
           

    QLabel {
    color: #333;
    font-size: 16px;
    font-weight: bold;
    padding: 6px 12px;
}
QComboBox {
                padding: 8px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                min-width: 200px;
                font-size: 14px;
            }

            QComboBox:hover {
                border-color: #2196F3;
            }

            QComboBox:focus {
                border-color: #1976D2;
                outline: none;
            }

            QComboBox::drop-down {
                width: 30px;
                border: none;
                background: transparent;
            }

            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                margin-right: 15px;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM0NDQ0NDQiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=);
            }

            QComboBox QAbstractItemView {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: transparent;
                outline: none;
                padding: 5px;
                margin-top: 5px;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px 15px;
                min-height: 25px;
                border-radius: 4px;
                margin: 2px 4px;
                color: #333333;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #E3F2FD;
                color: #1976D2;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #BBDEFB;
                color: #1565C0;
            }

            QComboBox QScrollBar:vertical {
                width: 8px;
                background: #F5F5F5;
                border-radius: 4px;
                margin: 0px;
            }

            QComboBox QScrollBar::handle:vertical {
                background: #BDBDBD;
                border-radius: 4px;
                min-height: 30px;
            }

            QComboBox QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }

            QComboBox QScrollBar::add-line:vertical,
            QComboBox QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QComboBox QScrollBar::add-page:vertical,
            QComboBox QScrollBar::sub-page:vertical {
                background: none;
            }QComboBox {
                padding: 8px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                min-width: 200px;
                font-size: 14px;
            }

            QComboBox:hover {
                border-color: #2196F3;
            }

            QComboBox:focus {
                border-color: #1976D2;
                outline: none;
            }

            QComboBox::drop-down {
                width: 30px;
                border: none;
                background: transparent;
            }

            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                margin-right: 15px;
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM0NDQ0NDQiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=);
            }

            QComboBox QAbstractItemView {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                selection-background-color: transparent;
                outline: none;
                padding: 5px;
                margin-top: 5px;
            }

            QComboBox QAbstractItemView::item {
                padding: 8px 15px;
                min-height: 25px;
                border-radius: 4px;
                margin: 2px 4px;
                color: #333333;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #E3F2FD;
                color: #1976D2;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #BBDEFB;
                color: #1565C0;
            }

            QComboBox QScrollBar:vertical {
                width: 8px;
                background: #F5F5F5;
                border-radius: 4px;
                margin: 0px;
            }

            QComboBox QScrollBar::handle:vertical {
                background: #BDBDBD;
                border-radius: 4px;
                min-height: 30px;
            }

            QComboBox QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }

            QComboBox QScrollBar::add-line:vertical,
            QComboBox QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QComboBox QScrollBar::add-page:vertical,
            QComboBox QScrollBar::sub-page:vertical {
                background: none;
            }

            
        """


        self.dark_style = """QMainWindow {
    background-color: #1e1e1e;
}

QLineEdit, QTextEdit {
    padding: 10px;
    border: 2px solid #444;
    border-radius: 5px;
    font-size: 14px;
    background-color: #2c2c2c;
    color: #ddd;
}

QPushButton {
    padding: 10px 20px;
    background-color: #3a7bd5;
    color: white;
    border: none;
    border-radius: 5px;
    font-size: 14px;
}

QPushButton:hover {
    background-color: #2a5ca8;
}

QListWidget {
    background-color: #2c2c2c;
    border: 2px solid #444;
    border-radius: 5px;
    padding: 5px;
    font-size: 14px;
    color: #ddd;
}

QListWidget::item {
    padding: 10px;
    margin: 2px 0;
    border-radius: 3px;
    background-color: #333;
    color: #ddd;
}

QListWidget::item:selected {
    background-color: #3a7bd5;
    color: white;
}

QScrollBar:vertical {
    border: none;
    background: #2c2c2c;
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #555;
    min-height: 30px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #777;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #2c2c2c;
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #555;
    min-width: 30px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background: #777;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
    width: 0px;
}

QLabel {
    color: #ddd;
    font-size: 16px;
    font-weight: bold;
    padding: 6px 12px;
}
"""
        self.setStyleSheet(self.light_style)


        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        self.is_dark_mode = False

        dashboard = QHBoxLayout()
        dashboard.setSpacing(10)
        dashboard.setContentsMargins(10, 10, 10, 10)

        set_lang_layout = QHBoxLayout()
        set_lang_layout.setSpacing(50)
        set_lang_layout.setContentsMargins(10, 10, 10, 10)

        self.theme_button = QPushButton("Toggle Theme")
        self.theme_button.clicked.connect(self.toggle_theme)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"


        if self.device == "cuda":
            self.helsinkinlp = True
        else:
            self.helsinkinlp = False

        self.helsinkinlp = False



        if  self.helsinkinlp:
            self.tokenizer_enja = MarianTokenizer.from_pretrained(helsinki_en_ja)
            self.model_enja = MarianMTModel.from_pretrained(helsinki_en_ja).to("cuda")

            self.tokenizer_jaen = MarianTokenizer.from_pretrained(helsinki_ja_en)
            self.model_jaen = MarianMTModel.from_pretrained(helsinki_ja_en).to("cuda")


        dashboard.addWidget(self.theme_button)


        main_layout.addLayout(dashboard)


        splitter = QSplitter(Qt.Horizontal)


        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(20)
        left_layout.setContentsMargins(20, 20, 20, 20)


        todo_title = QLabel("Notes")
        todo_title.setStyleSheet("font-size: 30px;")
        todo_title.setFont(QFont("Arial", 30, QFont.Bold))
        todo_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(todo_title)


        input_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add new note...")
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_task)
        input_layout.addWidget(self.task_input)
        input_layout.addWidget(self.add_button)
        left_layout.addLayout(input_layout)


        self.task_list = QListWidget()
        left_layout.addWidget(self.task_list)
        self.task_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.task_list.setHorizontalScrollMode(QListWidget.ScrollPerPixel)


        vertical_scrollbar = self.task_list.verticalScrollBar()
        vertical_scrollbar.setSingleStep(15)
        vertical_scrollbar.setPageStep(20)  


        button_layout = QHBoxLayout()
        self.complete_button = QPushButton("Complete")
        self.delete_button = QPushButton("Delete")
        self.complete_button.clicked.connect(self.complete_task)
        self.delete_button.clicked.connect(self.delete_task)
        button_layout.addWidget(self.complete_button)
        button_layout.addWidget(self.delete_button)
        left_layout.addLayout(button_layout)


        right_panel = QWidget()
        self.right_layout = QVBoxLayout(right_panel)
        self.right_layout.setSpacing(20)
        self.right_layout.setContentsMargins(20, 20, 20, 20)


        trans_title = QLabel("Translator")
        trans_title.setStyleSheet("font-size: 30px;")
        trans_title.setFont(QFont("Arial", 24, QFont.Bold))
        trans_title.setAlignment(Qt.AlignCenter)


        self.source_lang_text = "en"
        self.target_lang_text = "ja"
        self.right_layout.addWidget(trans_title)


        lang_layout = QHBoxLayout()
        

        self.source_lang = SearchableComboBox()
        self.target_lang = SearchableComboBox()
        self.langs_dict_google = GoogleTranslator().get_supported_languages(as_dict=True)

        

        self.source_lang.addItems(self.langs_dict_google.keys())
        self.target_lang.addItems(self.langs_dict_google.keys())
        

        self.source_lang.lineEdit().setPlaceholderText("Search source language...")
        self.target_lang.lineEdit().setPlaceholderText("Search target language...")
         
        
        self.source_lang.currentTextChanged.connect(self.on_source_lang_changed)
        self.target_lang.currentTextChanged.connect(self.on_target_lang_changed)







        source_container = QWidget()
        source_layout = QVBoxLayout(source_container)
        source_layout.addWidget(QLabel("Source Language:"))
        source_layout.addWidget(self.source_lang)

        swap_container = QWidget()
        swap_layout = QHBoxLayout(swap_container)
        swap_arrow = QPushButton("→")
        swap_arrow.clicked.connect(self.swap_languages)
        swap_layout.addWidget(swap_arrow)


        swap_layout.setContentsMargins(0, 40, 0, 0)


        target_container = QWidget()
        target_layout = QVBoxLayout(target_container)
        target_layout.addWidget(QLabel("Target Language:"))
        target_layout.addWidget(self.target_lang)

        lang_layout.addWidget(source_container)
        lang_layout.addWidget(swap_container)
        lang_layout.addWidget(target_container)


        self.right_layout.addLayout(lang_layout)



        self.prev_text = ""
        self.source_text = QTextEdit()
        self.source_text.setPlaceholderText("Enter text...")
        self.source_text.textChanged.connect(self.on_text_changed)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.translate_text)

        self.timer_auto_translate = QTimer(self)
        self.timer_auto_translate.timeout.connect(self.translate_text)
        self.timer_auto_translate.start(2000)

        self.thread_pool = QThreadPool()

       
        self.target_text = QTextEdit()
        self.target_text.setReadOnly(True)
        self.target_text.setStyleSheet("font-size: 18px;")
        self.source_text.setStyleSheet("font-size: 28px;")



        self.right_layout.addWidget(self.source_text)

        self.right_layout.addWidget(self.target_text)


        self.translate_button = QPushButton("Translate")
        self.translate_button.clicked.connect(self.translate_text)


        self.source_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.target_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


        self.source_lang.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.target_lang.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


        self.translate_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.translate_button.setMinimumHeight(50)



        speech2text_panel = Speech2TextWidget()


        left_panel.setMinimumWidth(450)
        right_panel.setMinimumWidth(625)
        speech2text_panel.setMinimumWidth(400)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.addWidget(speech2text_panel)


        window_width = self.width()
        panel_width = window_width // 3
        splitter.setSizes([panel_width, panel_width, panel_width])

        main_layout.addWidget(splitter)


        source_container = QWidget()
        source_layout = QHBoxLayout(source_container)
        source_layout.addWidget(self.source_text)

        source_tts_button = QPushButton()
        source_tts_button.setIcon(QIcon("speaker.png"))
        source_tts_button.setFixedSize(30, 30)
        source_tts_button.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    border-radius: 15px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
            """)
        source_tts_button.clicked.connect(
            lambda: self.speak_text(self.source_text.toPlainText(), self.source_lang_text)
        )
        source_layout.addWidget(source_tts_button)

        target_container = QWidget()
        target_layout = QHBoxLayout(target_container)
        target_layout.addWidget(self.target_text)

        target_tts_button = QPushButton()
        target_tts_button.setIcon(QIcon("speaker.png"))
        target_tts_button.setFixedSize(30, 30)
        target_tts_button.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    border-radius: 15px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
            """)
        target_tts_button.clicked.connect(
            lambda: self.speak_text(self.target_text.toPlainText(), self.target_lang_text)
        )
        target_layout.addWidget(target_tts_button)

        self.right_layout.addWidget(source_container)
        self.right_layout.addWidget(target_container)
        self.right_layout.addWidget(self.translate_button)
        self.load_tasks()


    def toggle_theme(self):
        if self.is_dark_mode:
            self.apply_light_theme()
        else:
            self.apply_dark_theme()
        self.is_dark_mode = not self.is_dark_mode

    def apply_light_theme(self):
        self.setStyleSheet(self.light_style)

    def apply_dark_theme(self):
        self.setStyleSheet(self.dark_style)


    def swap_languages(self):
        source_text = self.source_lang.currentText()
        target_text = self.target_lang.currentText()

        self.source_lang.setCurrentText(target_text)
        self.target_lang.setCurrentText(source_text)


        self.translate_text()




    
    def on_source_lang_changed(self, text):
        selected_code = self.langs_dict_google.get(text)
        self.source_lang_text = selected_code

        self.translate_text()
    
    def on_target_lang_changed(self, text):
        selected_code = self.langs_dict_google.get(text)
        self.target_lang_text = selected_code

        self.translate_text()
        
    
    def on_text_changed(self):
     input_text = self.source_text.toPlainText().strip()

     if not input_text:  
        self.target_text.clear()
        self.timer.stop()
     else:
        self.timer.start(50)

    
    

    def has_japanese(self, text):
        japanese_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
        return bool(re.search(japanese_pattern, text))

    def get_romaji(self, text):
        try:
            result = self.katsu.romaji(text)
            return result
        except:
            return None

    def translate_text(self):
        input_text = self.source_text.toPlainText().strip()
        source_lang = self.source_lang_text
        target_lang = self.target_lang_text

        if not input_text:
            return




        if (source_lang == "ja" and target_lang == "en"):
            if self.helsinkinlp:
                worker = TranslationWorker(input_text, source_lang, target_lang, [self.model_jaen, self.tokenizer_jaen])
            else:
                worker = TranslationWorker(input_text, source_lang, target_lang, [None, None])

        else:
            if (source_lang == "en" and target_lang == "ja"):
                if self.helsinkinlp:
                  worker = TranslationWorker(input_text, source_lang, target_lang, [self.model_enja, self.tokenizer_enja])
                else:
                    worker = TranslationWorker(input_text, source_lang, target_lang, [None, None])
            else:
                worker = TranslationWorker(input_text, source_lang, target_lang, [None, None])



        worker.signals.finished.connect(self.update_translation)
        self.thread_pool.start(worker)

    def update_translation(self, translated_text, is_html):
        """Çeviri tamamlandığında ana iş parçacığında GUI'yi güncelle"""
        if is_html:
            self.target_text.setHtml(translated_text)
        else:
            self.target_text.setPlainText(translated_text)


    def create_task_widget(self, text, romaji=None):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        text_container = QWidget()
        text_layout = QHBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)

        text_edit = QTextEdit()
        text_edit.setPlainText(text)
        text_edit.setReadOnly(True)
        text_edit.setMinimumHeight(50)
        text_edit.setWordWrapMode(True)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                padding: 12px;
                border-radius: 6px;
                font-size: 16px;
                color: #333;
            }
        """)


        tts_button = QPushButton()
        tts_button.setIcon(QIcon("speaker.png"))
        tts_button.setFixedSize(30, 30)
        tts_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                border-radius: 15px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)

        tts_button.clicked.connect(lambda: self.speak_text(text))

        text_layout.addWidget(text_edit)
        text_layout.addWidget(tts_button)
        layout.addWidget(text_container)
        translated_text = ""

        if romaji:
            romaji_container = QWidget()
            romaji_layout = QHBoxLayout(romaji_container)
            romaji_layout.setContentsMargins(0, 0, 0, 0)

            romaji_label = QLabel(romaji)
            romaji_label.setStyleSheet("""
                QLabel {
                    color: #666;
                    font-size: 14px;
                    font-style: italic;
                    padding: 8px;
                }
            """)
            romaji_label.setWordWrap(True)

            romaji_layout.addWidget(romaji_label)

            layout.addWidget(romaji_container)


            if self.helsinkinlp:
                inputs = self.tokenizer_jaen(text, return_tensors="pt", padding=True, truncation=True)
                translated = self.model_jaen.generate(**inputs.to("cuda"))
                translated_text = self.tokenizer_jaen.decode(translated[0], skip_special_tokens=True)
            else:
                translated_text = GoogleTranslator(source="ja", target="en").translate(text)

        else:
            lang = detect(text)
            print(lang)
            translated_text = GoogleTranslator(source=lang, target="en").translate(text)






        translated_container = QWidget()
        translated_layout = QHBoxLayout(translated_container)
        translated_layout.setContentsMargins(0, 0, 0, 0)

        translated_label = QLabel(translated_text)
        translated_label.setStyleSheet("""
                        QLabel {
                            color: #666;
                            font-size: 14px;
                            font-style: italic;
                            padding: 8px;
                        }
                    """)
        translated_label.setWordWrap(True)

        translated_layout.addWidget(translated_label)

        layout.addWidget(translated_container)


        widget.setLayout(layout)
        return widget


    def speak_text(self, text, lang=None):
        if text == self.target_text.toPlainText():
            text = text.split("\n")[0]

        if not text.strip():
            return

        if lang is None:
            lang = detect(text)


        self.tts_thread = TTSThread(text, lang)
        self.tts_thread.error.connect(self.on_tts_error)
        self.tts_thread.start()

    def on_tts_error(self, error_message):
        QMessageBox.warning(self, "TTS Error", f"Error during text-to-speech: {error_message}")
    

    def add_task(self):
     task_text = self.task_input.text().strip()
     print(task_text)
     if task_text:
        item = QListWidgetItem()
        romaji = None
        
        if self.has_japanese(task_text):
            romaji = self.get_romaji(task_text)
        
        task_widget = self.create_task_widget(task_text, romaji)
        
        item.setSizeHint(task_widget.sizeHint())
        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, task_widget)
        
        self.task_input.clear()
        self.save_tasks()

    def complete_task(self):
        current_item = self.task_list.currentItem()
        if current_item:
            widget = self.task_list.itemWidget(current_item)
            if widget:
                text_label = widget.findChild(QLabel)
                current_text = text_label.text()
                if current_text.startswith("✓ "):
                    text_label.setText(current_text[2:])
                else:
                    text_label.setText("✓ " + current_text)
            self.save_tasks()

    def delete_task(self):
        current_row = self.task_list.currentRow()
        if current_row >= 0:
            self.task_list.takeItem(current_row)
            self.save_tasks()

    def save_tasks(self):
     tasks = []
     for i in range(self.task_list.count()):
        item = self.task_list.item(i)
        widget = self.task_list.itemWidget(item)
        if widget:
            text_edit = widget.findChild(QTextEdit)
            romaji_label = widget.findChild(QLabel)
            
            if text_edit:
                text = text_edit.toPlainText()
            else:
                continue
            
            romaji = romaji_label.text() if romaji_label else None

            tasks.append({
                'text': text,
                'romaji': romaji,
                'completed': text.startswith("✓ ")
            })

     try:
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False)
     except Exception as e:
        QMessageBox.warning(self, "Error", f"Error saving tasks: {str(e)}")


    def load_tasks(self):
        try:
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
                for task in tasks:
                    item = QListWidgetItem()
                    task_widget = self.create_task_widget(task['text'], task['romaji'])
                    item.setSizeHint(task_widget.sizeHint())
                    self.task_list.addItem(item)
                    self.task_list.setItemWidget(item, task_widget)
        except FileNotFoundError:
            pass
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading tasks: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TodoApp()
    window.show()
    sys.exit(app.exec_())
