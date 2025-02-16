# EasyChat

Bu proje, kullanıcıların **pratik yapmak**, **not almak** ve **konuşmayı metne dökmek** gibi çeşitli görevleri yerine getirmelerini sağlayan bir PyQt5 uygulamasıdır. Uygulama üç ana bileşenden oluşmaktadır:

1. **Notes (Notlar)**: Kullanıcıların metin notları alıp düzenlemesine olanak tanır.
2. **Translator (Çevirmen)**: Kullanıcıların farklı diller arasında çeviri yapmasına imkan sağlar.
3. **Speech-to-Text (Konuşmadan Metne)**: Karşıdaki kişinin söylediklerini yazıya dökme fonksiyonu sunar.

## Özellikler

- **Notlar**: Kolayca not alabilir ve düzenleyebilirsiniz. Herhangi bir metni kaydedebilir ve sonra görüntüleyebilirsiniz.
- **Çeviri**: İki dil arasında metin çevirisi yapabilir. Bir dilde yazılan metni başka bir dile çevirebilirsiniz.
- **Konuşma Tanıma**: Mikrofon aracılığıyla bir kişinin söylediklerini gerçek zamanlı olarak metne dönüştürür.

## Kullanım

### Gereksinimler

- Python 3.x
- PyQt5
- Googletrans (veya başka bir çeviri kütüphanesi)
- SpeechRecognition (Konuşma tanıma için)

Gerekli kütüphaneleri yüklemek için aşağıdaki komutu çalıştırabilirsiniz:

```bash
git clone https://github.com/MRamazan/EasyChat
cd EasyChat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 interface.py


