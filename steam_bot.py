import requests
import json
import time
import os
from bs4 import BeautifulSoup # Yeni eklenen kütüphane

# --- AYARLAR ---
# Discord'dan aldığınız Webhook URL'sini buraya yapıştırın
# GitHub Secrets'tan alınacak
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# Kontrol sıklığı (saniye cinsinden). 7200 = 2 saat (Rate limit yememek için yüksek tutun)
KONTROL_ARALIGI = 7200 

# Bildirilen oyunları kaydetmek için dosya
BILDIRILEN_OYUNLAR_DOSYASI = "bildirilen_oyunlar.json"

# Takip edilecek Steam Etiket (Tag) ID'si
# 1685 = "Co-op" (Eşli)
# Diğer etiketler: 3841 = "Online Co-op", 7364 = "Local Co-op"
# İstediğiniz etiketin ID'sini Steam'de aratıp URL'den bulabilirsiniz.
STEAM_TAG_ID = "599" 
# --- AYARLAR SONU ---


def bildirilen_oyunlari_yukle():
    """Daha önce bildirimi yapılan oyunların listesini dosyadan okur."""
    if not os.path.exists(BILDIRILEN_OYUNLAR_DOSYASI):
        return set()
    try:
        with open(BILDIRILEN_OYUNLAR_DOSYASI, "r") as f:
            return set(json.load(f))
    except json.JSONDecodeError:
        print(f"Uyarı: {BILDIRILEN_OYUNLAR_DOSYASI} dosyası bozuk, sıfırlanıyor.")
        return set()

def bildirilen_oyunlari_kaydet(app_id_seti):
    """Bildirimi yapılan oyun listesini dosyaya yazar."""
    with open(BILDIRILEN_OYUNLAR_DOSYASI, "w") as f:
        json.dump(list(app_id_seti), f)

def discord_bildirimi_gonder(oyun_adi, app_id, indirim_yuzdesi, eski_fiyat, yeni_fiyat):
    """Formatlı bir Discord mesajı (embed) gönderir."""
    
    oyun_url = f"https://store.steampowered.com/app/{app_id}"
    
    # Fiyattaki 'TL' gibi para birimlerini temizle (varsa)
    eski_fiyat = eski_fiyat.strip()
    yeni_fiyat = yeni_fiyat.strip()
    
    data = {
        "content": f"🎉 **'Simülasyon' İndirim Alarmı!** 🎉",
        "embeds": [
            {
                "title": f"🎮 {oyun_adi}",
                "url": oyun_url,
                "description": f"Etiketle takibinizdeki bu oyun **%{indirim_yuzdesi}** indirime girdi!",
                "color": 65280,  # Yeşil renk
                "fields": [
                    { "name": "Eski Fiyat", "value": f"~~{eski_fiyat}~~", "inline": True },
                    { "name": "Yeni Fiyat", "value": f"**{yeni_fiyat}**", "inline": True }
                ],
                "thumbnail": {
                    "url": f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
                },
                "footer": {
                    "text": "Steam Store Scraper Bot"
                }
            }
        ]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
        print(f"Discord bildirimi gönderildi: {oyun_adi}")
    except requests.exceptions.RequestException as e:
        print(f"Discord'a gönderirken hata oluştu: {e}")

def indirimleri_kontrol_et():
    """Steam'deki 'Eşli' etiketiyle indirimleri kontrol eder."""
    
    print(f"Steam'deki 'Eşli' (Tag: {STEAM_TAG_ID}) indirimleri kontrol ediliyor...")
    bildirilen_oyunlar = bildirilen_oyunlari_yukle()
    
    # Sadece indirimde olan (specials=1) ve belirli bir etikete sahip (tags=...) oyunları arayan URL
    STEAM_SEARCH_URL = f"https://store.steampowered.com/search/?specials=1&tags={STEAM_TAG_ID}&l=turkish"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(STEAM_SEARCH_URL, headers=headers)
        
        if response.status_code != 200:
            print(f"Steam Mağazasına ulaşılamadı! Status Code: {response.status_code}")
            return
            
        # HTML içeriğini BeautifulSoup ile ayrıştır
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Arama sonuçlarındaki her bir oyun satırını bul
        # Steam bu sınıfı kullanıyor: 'search_result_row'
        oyun_satirlari = soup.find_all('a', class_='search_result_row')
        
        if not oyun_satirlari:
            print("Belirtilen etikette indirimli oyun bulunamadı.")
            return

        yeni_bildirim_yapildi = False

        for game in oyun_satirlari:
            # Oyunun App ID'sini al (data-ds-appid özelliğinden)
            app_id = game.get('data-ds-appid')
            
            # Eğer app_id yoksa veya daha önce bildirilmişse bu oyunu atla
            if not app_id or app_id in bildirilen_oyunlar:
                continue

            # Gerekli bilgileri HTML içinden çek
            oyun_adi_span = game.find('span', class_='title')
            indirim_span = game.find('div', class_='discount_pct')
            eski_fiyat_div = game.find('div', class_='discount_original_price')
            yeni_fiyat_div = game.find('div', class_='discount_final_price')

            # Bazen (örn. 'Oynaması Ücretsiz') oyunlarda fiyat bilgisi olmaz.
            # Gerekli tüm bilgiler varsa devam et.
            if not all([oyun_adi_span, indirim_span, eski_fiyat_div, yeni_fiyat_div]):
                continue
                
            oyun_adi = oyun_adi_span.text.strip()
            # indirim_yuzdesi: "-90%" şeklindedir, biz "90" istiyoruz
            indirim_yuzdesi = indirim_span.text.strip().replace('%', '').replace('-', '')
            eski_fiyat = eski_fiyat_div.text.strip()
            yeni_fiyat = yeni_fiyat_div.text.strip()
            
            # Bildirimi gönder
            discord_bildirimi_gonder(oyun_adi, app_id, indirim_yuzdesi, eski_fiyat, yeni_fiyat)
            
            bildirilen_oyunlar.add(app_id)
            yeni_bildirim_yapildi = True

        if yeni_bildirim_yapildi:
            bildirilen_oyunlari_kaydet(bildirilen_oyunlar)
        else:
            print("Yeni bir indirim bulunamadı.")

    except requests.exceptions.RequestException as e:
        print(f"Steam'e bağlanırken hata oluştu: {e}")
    except Exception as e:
        print(f"Bilinmeyen bir hata oluştu: {e}")

# --- Ana Döngü ---
if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("HATA: DISCORD_WEBHOOK secret'ı ayarlanmamış! GitHub Actions ayarlarını kontrol edin.")
    else:

        indirimleri_kontrol_et()

