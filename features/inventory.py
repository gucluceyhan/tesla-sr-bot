"""
Tesla Envanter Modülü
Envanter API'sinden veri çekme ve uygun araç seçimi
"""

import requests
import json
import time
import random
from typing import List, Optional, Dict, Any
from datetime import datetime
from fake_useragent import UserAgent

from core.config import (
    TeslaConfig, AracTercihi, RenkTercihi, 
    AracTipi, BolgeAyarlari
)


class EnvanterArac:
    """Envanterdeki araç bilgilerini temsil eden sınıf"""
    
    def __init__(self, data: Dict[str, Any]):
        self.vin = data.get('VIN', '')
        self.model = data.get('Model', '')
        self.trim = data.get('TrimName', '')
        self.renk = data.get('PAINT', {}).get('Code', '')
        self.koltuk_rengi = data.get('INTERIOR', {}).get('Code', '')
        self.fiyat = float(data.get('Price', 0))
        self.yil = data.get('Year', '')
        self.lokasyon = data.get('MetroName', '')
        self.menzil = data.get('TotalRange', 0)
        self.durum = data.get('InventoryStatus', '')
        self.teslimat_tarihi = data.get('ETA', '')
        self.ozellikler = data.get('OptionCodeList', [])
        self._raw_data = data
    
    def is_sr_model(self) -> bool:
        """SR (Standard Range) modeli mi kontrol et"""
        sr_indicators = ['Standard Range', 'SR', 'RWD']
        return any(indicator in self.trim for indicator in sr_indicators)
    
    def renk_uygun_mu(self, tercihler: List[RenkTercihi]) -> bool:
        """Araç rengi tercihlere uygun mu"""
        renk_map = {
            'red': RenkTercihi.KIRMIZI,
            'white': RenkTercihi.BEYAZ,
            'black': RenkTercihi.SIYAH,
            'blue': RenkTercihi.MAVI,
            'grey': RenkTercihi.GRI,
            'pearl': RenkTercihi.BEYAZ,  # Pearl white
            'solid': RenkTercihi.SIYAH,  # Solid black
        }
        
        arac_rengi = renk_map.get(self.renk.lower())
        return arac_rengi in tercihler if arac_rengi else False
    
    def fiyat_uygun_mu(self, max_fiyat: float) -> bool:
        """Fiyat limite uygun mu"""
        return self.fiyat <= max_fiyat
    
    def __repr__(self):
        return f"<EnvanterArac VIN={self.vin} Model={self.trim} Renk={self.renk} Fiyat={self.fiyat:,.0f} TL>"


class TeslaEnvanter:
    """Tesla envanter API ile etkileşim sınıfı"""
    
    def __init__(self, config: TeslaConfig):
        self.config = config
        self.session = requests.Session()
        self.ua = UserAgent()
        self._setup_session()
        
    def _setup_session(self):
        """Session ayarlarını yapılandır"""
        headers = BolgeAyarlari.HEADERS.copy()
        
        if self.config.bot.bot_korumalari:
            # Rastgele User-Agent kullan
            headers['User-Agent'] = self.ua.random
            
            # Ek bot koruma başlıkları
            headers.update({
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'sec-ch-ua': '"Google Chrome";v="120", "Chromium";v="120", "Not-A.Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
            })
        
        self.session.headers.update(headers)
    
    def _api_params(self) -> Dict[str, str]:
        """API çağrısı için gerekli parametreler"""
        return {
            'query': json.dumps({
                'model': 'my',  # Model Y
                'condition': 'new',
                'market': BolgeAyarlari.MARKET,
                'language': BolgeAyarlari.LANGUAGE,
                'super_region': BolgeAyarlari.SUPER_REGION,
                'options': {},
                'arrangeby': 'Price',
                'order': 'asc',
                'zip': self.config.tercih.teslimat_posta_kodu,
                'range': 0  # Tüm mesafeler
            }),
            'offset': '0',
            'count': '50',  # Maksimum sonuç sayısı
            'outsideOffset': '0',
            'outsideSearch': 'false'
        }
    
    def envanter_sorgula(self) -> List[EnvanterArac]:
        """Envanter API'sini sorgula ve araçları getir"""
        try:
            # Bot koruması için rastgele gecikme
            if self.config.bot.bot_korumalari:
                time.sleep(random.uniform(0.5, 2.0))
            
            # Önce ana API'yi dene
            api_url = BolgeAyarlari.INVENTORY_API
            
            response = self.session.get(
                api_url,
                params=self._api_params(),
                timeout=10
            )
            
            # Eğer 404 veya başka bir hata alırsak, alternatif URL'leri dene
            if response.status_code == 404:
                # Türkiye için alternatif URL'ler
                alternatif_urls = [
                    f"{BolgeAyarlari.BASE_URL}/inventory/api/v1/inventory-results",
                    f"{BolgeAyarlari.BASE_URL}/api/tesla/inventory",
                    "https://www.tesla.com/inventory/api/v1/inventory-results"
                ]
                
                for alt_url in alternatif_urls:
                    try:
                        if self.config.bot.debug_mod:
                            print(f"[DEBUG] Alternatif URL deneniyor: {alt_url}")
                        
                        response = self.session.get(
                            alt_url,
                            params=self._api_params(),
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            api_url = alt_url
                            print(f"[BILGI] Alternatif API endpoint kullanılıyor: {alt_url}")
                            break
                    except:
                        continue
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Türkiye'ye özel veri yapısı kontrolü
                if not results and 'data' in data:
                    results = data.get('data', {}).get('results', [])
                
                # Araçları EnvanterArac nesnelerine dönüştür
                araclar = [EnvanterArac(item) for item in results]
                
                if self.config.bot.debug_mod:
                    print(f"[DEBUG] {len(araclar)} araç bulundu")
                    print(f"[DEBUG] Kullanılan API: {api_url}")
                    
                return araclar
            else:
                print(f"[HATA] API yanıtı: {response.status_code}")
                if self.config.bot.debug_mod:
                    print(f"[DEBUG] Response headers: {response.headers}")
                    print(f"[DEBUG] Response text: {response.text[:500]}...")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"[HATA] API isteği başarısız: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            print(f"[HATA] JSON parse hatası: {str(e)}")
            return []
    
    def uygun_arac_bul(self) -> Optional[EnvanterArac]:
        """Kriterlere uygun araç bul"""
        araclar = self.envanter_sorgula()
        
        # SR modellerini filtrele
        sr_araclar = [arac for arac in araclar if arac.is_sr_model()]
        
        if self.config.bot.debug_mod:
            print(f"[DEBUG] {len(sr_araclar)} SR model bulundu")
        
        # Kriterlere göre filtrele
        uygun_araclar = []
        for arac in sr_araclar:
            # Fiyat kontrolü
            if not arac.fiyat_uygun_mu(self.config.tercih.maksimum_fiyat):
                continue
                
            # Renk kontrolü
            if not arac.renk_uygun_mu(self.config.tercih.renk_tercihi):
                continue
                
            # Stok durumu kontrolü
            if arac.durum not in ['Available', 'InTransit']:
                continue
                
            uygun_araclar.append(arac)
        
        if not uygun_araclar:
            return None
        
        # Renk tercihine göre sırala
        def renk_onceligi(arac):
            try:
                return self.config.tercih.renk_tercihi.index(
                    RenkTercihi(arac.renk.lower())
                )
            except (ValueError, AttributeError):
                return 999  # Bilinmeyen renk en sona
        
        uygun_araclar.sort(key=lambda x: (renk_onceligi(x), x.fiyat))
        
        secilen_arac = uygun_araclar[0]
        
        print(f"\n[BULUNDU] Uygun araç tespit edildi:")
        print(f"  VIN: {secilen_arac.vin}")
        print(f"  Model: {secilen_arac.trim}")
        print(f"  Renk: {secilen_arac.renk}")
        print(f"  Fiyat: {secilen_arac.fiyat:,.0f} TL")
        print(f"  Lokasyon: {secilen_arac.lokasyon}")
        print(f"  Teslimat: {secilen_arac.teslimat_tarihi}")
        
        return secilen_arac
    
    def surekli_kontrol(self, callback=None) -> Optional[EnvanterArac]:
        """Belirli aralıklarla envanter kontrolü yap"""
        deneme = 0
        baslangic_zamani = time.time()
        
        print(f"[BAŞLADI] Envanter kontrolü başladı...")
        print(f"  Kontrol aralığı: {self.config.bot.kontrol_araligi} saniye")
        print(f"  Maksimum deneme: {self.config.bot.maksimum_deneme}")
        
        while deneme < self.config.bot.maksimum_deneme:
            deneme += 1
            gecen_sure = time.time() - baslangic_zamani
            
            print(f"\n[KONTROL #{deneme}] Saat: {datetime.now().strftime('%H:%M:%S')}")
            
            # Satış saatini kontrol et
            if self._satis_saati_kontrolu():
                arac = self.uygun_arac_bul()
                
                if arac:
                    if callback:
                        callback(arac)
                    return arac
                else:
                    print(f"  Uygun araç bulunamadı")
            
            # Son deneme değilse bekle
            if deneme < self.config.bot.maksimum_deneme:
                # Rastgele varyasyon ekle (bot koruması)
                bekleme_suresi = self.config.bot.kontrol_araligi
                if self.config.bot.bot_korumalari:
                    bekleme_suresi += random.uniform(-1, 1)
                    bekleme_suresi = max(1, bekleme_suresi)  # En az 1 saniye
                
                print(f"  {bekleme_suresi:.1f} saniye bekleniyor...")
                time.sleep(bekleme_suresi)
        
        print(f"\n[BİTTİ] Maksimum deneme sayısına ulaşıldı")
        return None
    
    def _satis_saati_kontrolu(self) -> bool:
        """Satış saatinin gelip gelmediğini kontrol et"""
        satis_saati = datetime.strptime(
            self.config.bot.satis_baslangic_saati, 
            '%H:%M'
        ).time()
        
        simdiki_saat = datetime.now().time()
        
        # Satış saati henüz gelmemişse
        if simdiki_saat < satis_saati:
            kalan_dakika = (
                datetime.combine(datetime.today(), satis_saati) - 
                datetime.combine(datetime.today(), simdiki_saat)
            ).seconds // 60
            
            print(f"  Satış saatine {kalan_dakika} dakika kaldı ({self.config.bot.satis_baslangic_saati})")
            return False
        
        return True 