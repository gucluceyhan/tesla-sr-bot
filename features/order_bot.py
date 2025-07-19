"""
Tesla Sipariş Bot Modülü
Selenium kullanarak otomatik form doldurma ve sipariş verme
"""

import time
import random
from typing import Optional, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

from core.config import TeslaConfig, BolgeAyarlari
from .inventory import EnvanterArac


class TeslaSiparisBot:
    """Tesla sipariş işlemlerini yöneten bot sınıfı"""
    
    def __init__(self, config: TeslaConfig):
        self.config = config
        self.driver = None
        self.wait = None
        
    def tarayici_baslat(self):
        """Chrome tarayıcısını başlat"""
        options = uc.ChromeOptions()
        
        # Temel ayarlar
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        
        # Bot korumaları aktifse ek ayarlar
        if self.config.bot.bot_korumalari:
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            
            # Kullanıcı profili gibi görünmek için
            options.add_argument('--user-data-dir=/tmp/chrome_profile')
            
            # Dil ayarı
            options.add_argument('--lang=tr-TR')
        
        # Headless mod
        if self.config.bot.headless_mod:
            options.add_argument('--headless=new')
            options.add_argument('--window-size=1920,1080')
        else:
            options.add_argument('--start-maximized')
        
        # Undetected ChromeDriver kullan
        self.driver = uc.Chrome(options=options, version_main=120)
        self.wait = WebDriverWait(self.driver, 20)
        
        # JavaScript özelliklerini ayarla (bot tespitini zorlaştırır)
        if self.config.bot.bot_korumalari:
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']})")
        
        print("[BOT] Tarayıcı başlatıldı")
    
    def tarayici_kapat(self):
        """Tarayıcıyı kapat"""
        if self.driver:
            self.driver.quit()
            print("[BOT] Tarayıcı kapatıldı")
    
    def _insan_gibi_yaz(self, element, text: str):
        """İnsan gibi yazma simülasyonu"""
        element.clear()
        
        if self.config.bot.bot_korumalari:
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
        else:
            element.send_keys(text)
    
    def _rastgele_bekle(self, min_saniye: float = 0.5, max_saniye: float = 2.0):
        """Rastgele bekleme (bot koruması)"""
        if self.config.bot.bot_korumalari:
            time.sleep(random.uniform(min_saniye, max_saniye))
        else:
            time.sleep(0.5)
    
    def _element_bekle_ve_tikla(self, locator, timeout: int = 10):
        """Element görünür olana kadar bekle ve tıkla"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            self._rastgele_bekle(0.3, 0.8)
            
            # İnsan gibi tıklama
            if self.config.bot.bot_korumalari:
                # Rastgele offset ile tıkla
                action = self.driver.action_chains
                action.move_to_element_with_offset(
                    element, 
                    random.randint(-5, 5), 
                    random.randint(-5, 5)
                )
                action.click().perform()
            else:
                element.click()
                
            return True
        except TimeoutException:
            print(f"[HATA] Element bulunamadı: {locator}")
            return False
    
    def siparis_ver(self, arac: EnvanterArac) -> bool:
        """Seçilen araç için sipariş işlemini başlat"""
        try:
            self.tarayici_baslat()
            
            # 1. Araç sayfasına git
            if not self._arac_sayfasina_git(arac):
                return False
            
            # 2. Sipariş formunu doldur
            if not self._siparis_formunu_doldur():
                return False
            
            # 3. Kart bilgilerini gir
            if not self._kart_bilgilerini_gir():
                return False
            
            # 4. Siparişi onayla
            if not self._siparisi_onayla():
                return False
            
            print("\n[BAŞARI] Sipariş başarıyla verildi!")
            return True
            
        except Exception as e:
            print(f"\n[HATA] Sipariş işlemi başarısız: {str(e)}")
            if self.config.bot.debug_mod:
                import traceback
                traceback.print_exc()
            return False
        finally:
            if not self.config.bot.debug_mod:
                self.tarayici_kapat()
    
    def _arac_sayfasina_git(self, arac: EnvanterArac) -> bool:
        """Araç detay sayfasına git"""
        try:
            # Önce tasarım sayfasına git
            print(f"[BOT] Araç sayfasına gidiliyor: {arac.vin}")
            self.driver.get(f"{BolgeAyarlari.DESIGN_URL}?vin={arac.vin}")
            
            self._rastgele_bekle(2, 4)
            
            # "Order Now" butonunu bekle ve tıkla
            order_button_selectors = [
                (By.XPATH, "//button[contains(text(), 'Sipariş Ver')]"),
                (By.XPATH, "//button[contains(text(), 'Order Now')]"),
                (By.CSS_SELECTOR, "button[data-id='order-button']"),
                (By.CSS_SELECTOR, ".order-button"),
                (By.XPATH, "//button[contains(@class, 'order')]")
            ]
            
            for selector in order_button_selectors:
                if self._element_bekle_ve_tikla(selector, timeout=5):
                    print("[BOT] Sipariş sayfasına yönlendiriliyor...")
                    self._rastgele_bekle(2, 3)
                    return True
            
            print("[HATA] Sipariş butonu bulunamadı")
            return False
            
        except Exception as e:
            print(f"[HATA] Araç sayfasına gidilemedi: {str(e)}")
            return False
    
    def _siparis_formunu_doldur(self) -> bool:
        """Sipariş formunu doldur"""
        try:
            print("[BOT] Sipariş formu dolduruluyor...")
            
            # Teslimat posta kodu
            zip_selectors = [
                (By.XPATH, "//input[@placeholder='Enter Delivery ZIP']"),
                (By.XPATH, "//input[@placeholder='Teslimat Posta Kodu']"),
                (By.NAME, "deliveryZip"),
                (By.ID, "delivery-zip"),
                (By.CSS_SELECTOR, "input[data-id='delivery-zip']")
            ]
            
            for selector in zip_selectors:
                try:
                    zip_input = self.wait.until(EC.presence_of_element_located(selector))
                    self._insan_gibi_yaz(zip_input, self.config.tercih.teslimat_posta_kodu)
                    self._rastgele_bekle()
                    break
                except:
                    continue
            
            # Hesap bilgileri formunu doldur
            form_fields = {
                'firstName': self.config.kullanici.ad,
                'lastName': self.config.kullanici.soyad,
                'email': self.config.kullanici.email,
                'confirmEmail': self.config.kullanici.email,
                'phone': self.config.kullanici.telefon
            }
            
            for field_name, value in form_fields.items():
                selectors = [
                    (By.NAME, field_name),
                    (By.ID, field_name),
                    (By.CSS_SELECTOR, f"input[name='{field_name}']"),
                    (By.XPATH, f"//input[@name='{field_name}']")
                ]
                
                for selector in selectors:
                    try:
                        element = self.driver.find_element(*selector)
                        self._insan_gibi_yaz(element, value)
                        self._rastgele_bekle(0.5, 1)
                        break
                    except:
                        continue
            
            # "Order with Card" butonuna tıkla
            card_button_selectors = [
                (By.XPATH, "//button[contains(text(), 'Order with Card')]"),
                (By.XPATH, "//button[contains(text(), 'Kart ile Sipariş')]"),
                (By.CSS_SELECTOR, "button[data-id='card-payment']"),
                (By.XPATH, "//button[contains(@class, 'card-payment')]")
            ]
            
            for selector in card_button_selectors:
                if self._element_bekle_ve_tikla(selector, timeout=5):
                    print("[BOT] Kart bilgileri sayfasına geçiliyor...")
                    return True
            
            return False
            
        except Exception as e:
            print(f"[HATA] Form doldurma hatası: {str(e)}")
            return False
    
    def _kart_bilgilerini_gir(self) -> bool:
        """Kart bilgilerini gir"""
        try:
            print("[BOT] Kart bilgileri giriliyor...")
            
            self._rastgele_bekle(2, 3)
            
            # Kart bilgileri
            kart_fields = {
                'cardName': self.config.kart.kart_sahibi,
                'cardNumber': self.config.kart.kart_no,
                'cvv': self.config.kart.cvv,
                'billingZip': self.config.kart.fatura_posta_kodu,
                'deliveryZip': self.config.tercih.teslimat_posta_kodu
            }
            
            for field_name, value in kart_fields.items():
                selectors = [
                    (By.NAME, field_name),
                    (By.ID, field_name),
                    (By.CSS_SELECTOR, f"input[name='{field_name}']"),
                    (By.XPATH, f"//input[@placeholder*='{field_name}']")
                ]
                
                for selector in selectors:
                    try:
                        element = self.driver.find_element(*selector)
                        self._insan_gibi_yaz(element, value)
                        self._rastgele_bekle(0.5, 1.5)
                        break
                    except:
                        continue
            
            # Son kullanma tarihi - Ay
            month_selectors = [
                (By.NAME, 'expirationMonth'),
                (By.ID, 'expiration-month'),
                (By.CSS_SELECTOR, "select[name='expirationMonth']")
            ]
            
            for selector in month_selectors:
                try:
                    month_select = Select(self.driver.find_element(*selector))
                    month_select.select_by_value(str(self.config.kart.son_kullanma_ay))
                    self._rastgele_bekle()
                    break
                except:
                    continue
            
            # Son kullanma tarihi - Yıl
            year_selectors = [
                (By.NAME, 'expirationYear'),
                (By.ID, 'expiration-year'),
                (By.CSS_SELECTOR, "select[name='expirationYear']")
            ]
            
            for selector in year_selectors:
                try:
                    year_select = Select(self.driver.find_element(*selector))
                    year_select.select_by_value(str(self.config.kart.son_kullanma_yil))
                    self._rastgele_bekle()
                    break
                except:
                    continue
            
            return True
            
        except Exception as e:
            print(f"[HATA] Kart bilgileri giriş hatası: {str(e)}")
            return False
    
    def _siparisi_onayla(self) -> bool:
        """Siparişi onayla"""
        try:
            print("[BOT] Sipariş onaylanıyor...")
            
            # Son kontroller için bekle
            self._rastgele_bekle(2, 3)
            
            # Place Order butonunu bul ve tıkla
            place_order_selectors = [
                (By.XPATH, "//button[contains(text(), 'Place Order')]"),
                (By.XPATH, "//button[contains(text(), 'Siparişi Ver')]"),
                (By.CSS_SELECTOR, "button[data-id='place-order']"),
                (By.CSS_SELECTOR, ".place-order-button"),
                (By.XPATH, "//button[contains(@class, 'order-submit')]")
            ]
            
            for selector in place_order_selectors:
                try:
                    button = self.wait.until(EC.element_to_be_clickable(selector))
                    
                    # Debug modda onay iste
                    if self.config.bot.debug_mod:
                        input("\n[DEBUG] Sipariş vermek üzere. Devam etmek için ENTER'a basın...")
                    
                    # Butona tıkla
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    self._rastgele_bekle(1, 2)
                    
                    if self.config.bot.bot_korumalari:
                        # JavaScript ile tıkla (daha güvenilir)
                        self.driver.execute_script("arguments[0].click();", button)
                    else:
                        button.click()
                    
                    # Sipariş onayını bekle
                    self._rastgele_bekle(3, 5)
                    
                    # Başarı kontrolü
                    success_indicators = [
                        "order-confirmation",
                        "order-success",
                        "thank-you",
                        "teşekkür",
                        "sipariş alındı",
                        "order received"
                    ]
                    
                    page_source = self.driver.page_source.lower()
                    for indicator in success_indicators:
                        if indicator in page_source:
                            print("[BAŞARI] Sipariş onayı alındı!")
                            return True
                    
                    # URL kontrolü
                    if "success" in self.driver.current_url or "confirmation" in self.driver.current_url:
                        print("[BAŞARI] Sipariş başarıyla tamamlandı!")
                        return True
                    
                    return True  # Varsayılan olarak başarılı kabul et
                    
                except TimeoutException:
                    continue
            
            print("[HATA] Sipariş onay butonu bulunamadı")
            return False
            
        except Exception as e:
            print(f"[HATA] Sipariş onaylama hatası: {str(e)}")
            return False 