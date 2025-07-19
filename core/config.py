"""
Tesla Bot Konfigürasyon Modülü
Kullanıcı hesabı, kart bilgisi ve araç tercihleri için veri modelleri
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RenkTercihi(str, Enum):
    """Araç renk seçenekleri"""
    KIRMIZI = "red"
    STANDART = "standard"
    BEYAZ = "white"
    SIYAH = "black"
    MAVI = "blue"
    GRI = "grey"


class KoltukRengi(str, Enum):
    """Koltuk rengi seçenekleri"""
    STANDART = "standard"
    BEYAZ = "white"
    SIYAH = "black"


class AracTipi(str, Enum):
    """Araç tipi seçenekleri"""
    SR = "Standard Range"
    LR = "Long Range"
    PERF = "Performance"


class KullaniciHesabi(BaseModel):
    """Tesla hesap bilgileri"""
    ad: str = Field(..., min_length=2, description="Kullanıcı adı")
    soyad: str = Field(..., min_length=2, description="Kullanıcı soyadı")
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', description="E-posta adresi")
    telefon: str = Field(..., pattern=r'^\+?[0-9]{10,15}$', description="Telefon numarası")
    
    @validator('telefon')
    def telefon_formati(cls, v):
        # Türkiye telefon numarası formatına dönüştür
        if not v.startswith('+'):
            if v.startswith('0'):
                v = '+9' + v
            else:
                v = '+90' + v
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "ad": "Gizem",
                "soyad": "Türkoğlu",
                "email": "gizem.turkoglu@gmail.com",
                "telefon": "+905056919179"
            }
        }


class KartBilgisi(BaseModel):
    """Ödeme kartı bilgileri"""
    kart_sahibi: str = Field(..., min_length=3, description="Kart üzerindeki isim")
    kart_no: str = Field(..., pattern=r'^[0-9]{16}$', description="16 haneli kart numarası")
    son_kullanma_ay: int = Field(..., ge=1, le=12, description="Son kullanma ayı (1-12)")
    son_kullanma_yil: int = Field(..., ge=datetime.now().year, description="Son kullanma yılı")
    cvv: str = Field(..., pattern=r'^[0-9]{3}$', description="3 haneli güvenlik kodu")
    fatura_posta_kodu: str = Field(..., pattern=r'^[0-9]{5}$', description="Fatura posta kodu")
    
    @validator('kart_no')
    def kart_no_dogrula(cls, v):
        # Basit Luhn algoritması kontrolü
        def luhn_check(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10 == 0
        
        if not luhn_check(v):
            raise ValueError('Geçersiz kart numarası')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "kart_sahibi": "AHMET YILMAZ",
                "kart_no": "4532123456789012",
                "son_kullanma_ay": 12,
                "son_kullanma_yil": 2025,
                "cvv": "123",
                "fatura_posta_kodu": "34000"
            }
        }


class AracTercihi(BaseModel):
    """Araç tercihleri ve limitler"""
    arac_tipi: AracTipi = Field(default=AracTipi.SR, description="Araç tipi")
    maksimum_fiyat: float = Field(..., gt=0, description="Maksimum fiyat limiti (TL)")
    renk_tercihi: List[RenkTercihi] = Field(
        default=[RenkTercihi.KIRMIZI, RenkTercihi.STANDART],
        description="Renk tercihleri (öncelik sırasına göre)"
    )
    koltuk_rengi_kurali: bool = Field(
        default=True,
        description="Otomatik koltuk rengi kuralı (kırmızı araç=standart, diğer=beyaz)"
    )
    teslimat_posta_kodu: str = Field(..., pattern=r'^[0-9]{5}$', description="Teslimat posta kodu")
    
    def koltuk_rengini_belirle(self, arac_rengi: str) -> KoltukRengi:
        """Araç rengine göre koltuk rengini belirle"""
        if self.koltuk_rengi_kurali:
            if arac_rengi == RenkTercihi.KIRMIZI:
                return KoltukRengi.STANDART
            else:
                return KoltukRengi.BEYAZ
        return KoltukRengi.STANDART
    
    class Config:
        schema_extra = {
            "example": {
                "arac_tipi": "Standard Range",
                "maksimum_fiyat": 2000000.0,
                "renk_tercihi": ["red", "standard"],
                "koltuk_rengi_kurali": True,
                "teslimat_posta_kodu": "06660"
            }
        }


class BotAyarlari(BaseModel):
    """Bot çalışma ayarları"""
    kontrol_araligi: int = Field(default=5, ge=1, le=60, description="Envanter kontrol aralığı (saniye)")
    maksimum_deneme: int = Field(default=100, ge=1, description="Maksimum deneme sayısı")
    bot_korumalari: bool = Field(default=True, description="Bot tespit korumaları aktif")
    headless_mod: bool = Field(default=False, description="Tarayıcı headless modda çalışsın")
    debug_mod: bool = Field(default=False, description="Debug modunda çalıştır")
    satis_baslangic_saati: str = Field(default="17:59", pattern=r'^[0-2][0-9]:[0-5][0-9]$', description="Satış başlangıç saati")
    
    class Config:
        schema_extra = {
            "example": {
                "kontrol_araligi": 5,
                "maksimum_deneme": 100,
                "bot_korumalari": True,
                "headless_mod": False,
                "debug_mod": False,
                "satis_baslangic_saati": "17:59"
            }
        }


class TeslaConfig(BaseModel):
    """Ana konfigürasyon sınıfı"""
    kullanici: KullaniciHesabi
    kart: KartBilgisi
    tercih: AracTercihi
    bot: BotAyarlari = Field(default_factory=BotAyarlari)
    
    class Config:
        schema_extra = {
            "example": {
                "kullanici": KullaniciHesabi.Config.schema_extra["example"],
                "kart": KartBilgisi.Config.schema_extra["example"],
                "tercih": AracTercihi.Config.schema_extra["example"],
                "bot": BotAyarlari.Config.schema_extra["example"]
            }
        }


# Bölgesel ayarlar
class BolgeAyarlari:
    """Türkiye bölgesi için sabit ayarlar"""
    BASE_URL = "https://www.tesla.com/tr_TR"
    INVENTORY_API = "https://www.tesla.com/tr_TR/api/tesla/inventory/tesla"
    ORDER_URL = "https://www.tesla.com/tr_TR/modely/order"
    DESIGN_URL = "https://www.tesla.com/tr_TR/modely/design#overview"
    
    MARKET = "TR"
    LANGUAGE = "tr"
    SUPER_REGION = "europe"
    CURRENCY = "TRY"
    
    # API Headers
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Referer": BASE_URL,
        "Origin": BASE_URL
    } 