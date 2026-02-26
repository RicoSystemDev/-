#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РИКО И ЕГО ТУРЕЛИ
Версия 2.6.1 - точное позиционирование сервы
"""

import json
import time
import threading
import os
from datetime import datetime
from enum import Enum

# Импорты для Arduino
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("⚠️ pyserial не установлен. Управление Arduino отключено.")
    print("   Установи: pip install pyserial")

# Импорты для звука
try:
    import pygame
    pygame.mixer.init()
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False
    print("⚠️ pygame не установлен. Звук будет в текстовом режиме.")

# Импорты для распознавания лиц
try:
    from facedb import FaceDB
    import cv2
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("⚠️ FaceDB не установлена. Распознавание лиц отключено.")

# ====================== КОНФИГУРАЦИЯ ======================

class Config:
    EXPELL_TIME = 2.5
    DEBT_REMINDER_DAYS = 3
    DEBT_WARNING_DAYS = 7
    DEBT_REPORT_DAYS = 14
    DEBT_PARENTS_DAYS = 21

    FAMILY_RULES_FILE = "family_rules.json"
    ITEMS_DATABASE_FILE = "items.json"
    STATISTICS_FILE = "stats.json"
    LOG_FILE = "system.log"

# ====================== СОСТОЯНИЯ ======================

class ThreatLevel(Enum):
    OBSERVE = 1
    ATTENTION = 2
    WARNING = 3
    DANGER = 4
    CRITICAL = 5

class PersonState(Enum):
    NORMAL = "normal"
    DISTRESSED = "distressed"
    ANGRY = "angry"
    SICK = "sick"

class TurretMode(Enum):
    HIDDEN = "hidden"
    ACTIVE = "active"
    RESERVE = "reserve"
    RELOADING = "reloading"
    AIMING = "aiming"

# ====================== ОСНОВНОЙ КЛАСС ======================

class RicoTurretSystem:
    """
    Единая система управления мастерской Рико
    Версия 2.6.1 - точное позиционирование сервы
    """
    
    def __init__(self, name="Рико", use_camera=False):
        self.name = name
        self.nickname = "Рико"
        self.use_camera = use_camera
        
        self.threat_level = ThreatLevel.OBSERVE
        self.system_active = True
        self.silent_mode = False
        
        self.turrets = self.init_turrets()
        
        self.family_rules = self.load_family_rules()
        self.items_db = self.load_items_database()
        self.stats = self.load_statistics()
        
        self.face_db = None
        self.camera = None
        self.init_face_recognition()
        
        self.arduino = None
        self.init_arduino()
        
        self.people_in_zone = {}
        self.logs = []
        
        print(f"\n{'='*50}")
        print(f"🤖 СИСТЕМА {self.name.upper()} И ЕГО ТУРЕЛИ")
        print(f"{'='*50}")
        print(f"Версия 2.6.1 - точное позиционирование")
        if self.face_db:
            print(f"📸 Загружено лиц в базу: {self.face_db.count()}")
        else:
            print(f"📸 Распознавание лиц: отключено")
        print(f"🔊 Звук: {'доступен' if SOUND_AVAILABLE else 'только текст'}")
        print(f"🔌 Arduino: {'подключена' if self.arduino else 'не найдена'}")
        print(f"Загружено правил: {len(self.family_rules)}")
        print(f"Загружено предметов: {len(self.items_db)}")
        print(f"Статус: АКТИВНА")
        print(f"{'='*50}\n")
        
        self.log_event("Система запущена")
    
    def init_turrets(self):
        return {
            "main_1": {"ammo": 150, "mode": TurretMode.ACTIVE, "position": "у стола"},
            "main_2": {"ammo": 150, "mode": TurretMode.ACTIVE, "position": "у полок"},
            "hidden_1": {"ammo": 100, "mode": TurretMode.RESERVE, "position": "за шкафом"},
            "hidden_2": {"ammo": 100, "mode": TurretMode.RESERVE, "position": "под столом"}
        }
    
    def init_arduino(self):
        if not SERIAL_AVAILABLE:
            return
        
        possible_ports = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7']
        for port in possible_ports:
            try:
                self.arduino = serial.Serial(port, 9600, timeout=1)
                time.sleep(2)
                print(f"✅ Arduino найдена на {port}")
                return
            except:
                continue
        
        print("⚠️ Arduino не найдена. Проверь подключение и порт.")
        self.arduino = None
    
    def set_servo_angle(self, angle):
        if self.arduino is None:
            print("❌ Arduino не подключена")
            return False
        
        try:
            angle = int(angle)
            if angle < 0 or angle > 180:
                print("⚠️ Угол должен быть от 0 до 180")
                return False
            
            self.arduino.write(f"{angle}\n".encode())
            print(f"🔧 Угол {angle}° отправлен на Arduino")
            return True
        except ValueError:
            print("⚠️ Введи число, например: угол 90")
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False
    
    def test_servo(self):
        if self.arduino is None:
            print("❌ Arduino не подключена")
            return
        
        print("🔧 Автотест серво:")
        angles = [0, 90, 180]
        
        for angle in angles:
            print(f"  → {angle}°")
            self.set_servo_angle(angle)
            time.sleep(1.5)
        
        print("  → Возврат в 90°")
        self.set_servo_angle(90)
        time.sleep(1)
        print("✅ Тест завершён")
    
    def precise_angle(self, angle, hold_time=0):
        if self.arduino is None:
            print("❌ Arduino не подключена")
            return False
        
        try:
            angle = int(angle)
            if angle < 0 or angle > 180:
                print("⚠️ Угол должен быть от 0 до 180")
                return False
            
            self.arduino.write(f"{angle}\n".encode())
            print(f"🔧 Угол {angle}° установлен")
            
            if hold_time > 0:
                print(f"⏱️ Удержание {hold_time} сек...")
                time.sleep(hold_time)
                self.arduino.write(f"90\n".encode())
                print(f"🔧 Возврат в 90°")
            
            return True
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False
    
    def init_face_recognition(self):
        if not FACE_RECOGNITION_AVAILABLE:
            return
        
        try:
            self.face_db = FaceDB(path="facedata")
            if self.use_camera:
                self.camera = cv2.VideoCapture(0)
                if not self.camera.isOpened():
                    self.use_camera = False
        except Exception as e:
            print(f"⚠️ Ошибка инициализации FaceDB: {e}")
            self.face_db = None
    
    def identify_person_from_camera(self):
        if not self.use_camera or self.camera is None:
            return None
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                return None
            
            temp_path = "temp_face.jpg"
            cv2.imwrite(temp_path, frame)
            
            result = self.face_db.recognize(
                img=temp_path,
                include=['name', 'real_name', 'rule']
            )
            
            try:
                os.remove(temp_path)
            except:
                pass
            
            return result
        except Exception as e:
            print(f"❌ Ошибка распознавания: {e}")
            return None
    
    def identify_person(self, face_image=None):
        if self.face_db and self.use_camera:
            result = self.identify_person_from_camera()
            if result:
                person_id = result['name']
                print(f"✅ Распознан: {result.get('real_name', person_id)}")
                return person_id
        return None
    
    def load_family_rules(self):
        default_rules = {
            "rico": {
                "name": "Рико",
                "type": "owner",
                "knock_required": False,
                "warning_time": 0,
                "nerfs": False,
                "description": "Хозяин мастерской"
            },
            "sister": {
                "name": "Сестра",
                "type": "sister",
                "personality": "неадекватная",
                "knock_required": True,
                "warning_time": Config.EXPELL_TIME,
                "nerfs": True,
                "description": "Лезущая куда не надо"
            },
            "dad": {
                "name": "Папа",
                "type": "parent",
                "knock_required": True,
                "warning_time": 0,
                "nerfs": False,
                "description": "Главный инженер (после Рико)"
            },
            "mom": {
                "name": "Мама",
                "type": "parent",
                "knock_required": True,
                "warning_time": 0,
                "nerfs": False,
                "description": "Главный по еде"
            },
            "brother_young": {
                "name": "Младший брат",
                "type": "child",
                "personality": "маленький",
                "knock_required": False,
                "warning_time": 0,
                "nerfs": False,
                "description": "Поблажки до 7 лет"
            }
        }
        
        if os.path.exists(Config.FAMILY_RULES_FILE):
            with open(Config.FAMILY_RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(Config.FAMILY_RULES_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_rules, f, indent=2, ensure_ascii=False)
            return default_rules
    
    def load_items_database(self):
        default_items = {
            "отвёртка": {
                "location": "верстак, третий ящик",
                "description": "крестовая, длина 150 мм",
                "owner": "Рико",
                "borrowed_by": None,
                "borrow_date": None,
                "borrow_count": 0,
                "return_count": 0
            },
            "паяльник": {
                "location": "полка над столом",
                "description": "60 Вт, с регулировкой",
                "owner": "Рико",
                "borrowed_by": None,
                "borrow_date": None,
                "borrow_count": 0,
                "return_count": 0
            },
            "мультиметр": {
                "location": "ящик стола, слева",
                "description": "цифровой, Mastech",
                "owner": "Рико",
                "borrowed_by": None,
                "borrow_date": None,
                "borrow_count": 0,
                "return_count": 0
            }
        }
        
        if os.path.exists(Config.ITEMS_DATABASE_FILE):
            with open(Config.ITEMS_DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(Config.ITEMS_DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_items, f, indent=2, ensure_ascii=False)
            return default_items
    
    def load_statistics(self):
        default_stats = {
            "total_entries": 0,
            "total_warnings": 0,
            "total_nerf_shots": 0,
            "expel_count": 0,
            "items_borrowed": 0,
            "items_returned": 0,
            "debt_reminders": 0,
            "by_person": {}
        }
        
        if os.path.exists(Config.STATISTICS_FILE):
            with open(Config.STATISTICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(Config.STATISTICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_stats, f, indent=2)
            return default_stats
    
    def get_person_rule(self, person_id):
        if person_id in self.family_rules:
            return self.family_rules[person_id]
        else:
            return self.family_rules["sister"]
    
    def person_at_door(self, person_id, knocked=False):
        if person_id is None:
            print("❌ Человек не распознан")
            return False
        
        rule = self.get_person_rule(person_id)
        person_name = rule.get("name", person_id)
        person_type = rule.get("type", "unknown")
        
        self.log_event(f"🚪 {person_name} у двери. Стук: {'да' if knocked else 'нет'}")
        
        if person_id not in self.stats["by_person"]:
            self.stats["by_person"][person_id] = {"entries": 0, "warnings": 0, "nerfs": 0}
        self.stats["by_person"][person_id]["entries"] += 1
        self.stats["total_entries"] += 1
        
        if person_type == "parent":
            if not knocked:
                self.play_sound("warning")
                self.say(f"{person_name}, пожалуйста, стучитесь в следующий раз.")
            self.allow_entry(person_id)
            return True
        
        if rule.get("knock_required", False) and not knocked:
            self.play_sound("warning")
            self.fire_nerf(person_id, reason="без стука")
            return False
        
        self.allow_entry(person_id)
        return True
    
    def allow_entry(self, person_id):
        rule = self.get_person_rule(person_id)
        person_name = rule.get("name", person_id)
        
        self.log_event(f"✅ {person_name} разрешён вход")
        self.say(f"Проходи, {person_name}. Руки прочь от стола.")
        
        self.people_in_zone[person_id] = {
            "entered_at": time.time(),
            "position": "door"
        }
    
    def fire_nerf(self, person_id, reason=""):
        rule = self.get_person_rule(person_id)
        person_name = rule.get("name", person_id)
        
        if not rule.get("nerfs", True):
            self.log_event(f"⚠️ {person_name}: полагался выстрел, но запрещено правилами")
            return False
        
        self.log_event(f"🔫 ВЫСТРЕЛ по {person_name}! Причина: {reason}")
        self.play_sound("fire")
        
        self.stats["total_nerf_shots"] += 1
        if person_id in self.stats["by_person"]:
            self.stats["by_person"][person_id]["nerfs"] += 1
        
        return True
    
    def fire_all_turrets(self, target_person):
        rule = self.get_person_rule(target_person)
        person_name = rule.get("name", target_person)
        
        self.log_event(f"🔥 ЗАЛП из всех турелей по {person_name}!")
        self.play_sound("fire")
        self.play_sound("fire")
        
        self.stats["total_nerf_shots"] += 4
        self.stats["expel_count"] += 1
    
    def expel_button_pressed(self):
        self.log_event("🚨 НАЖАТА КНОПКА 'ПРОГНАТЬ'")
        
        if "sister" in self.people_in_zone:
            rule = self.get_person_rule("sister")
            warning_time = rule.get("warning_time", Config.EXPELL_TIME)
            
            self.play_sound("aiming")
            self.say(f"Сестра, у вас {warning_time} секунд, чтобы покинуть помещение. По команде Рико.")
            
            start_time = time.time()
            while time.time() - start_time < warning_time:
                time.sleep(0.1)
            
            if "sister" in self.people_in_zone:
                self.fire_all_turrets("sister")
                self.say("Цель поражена.")
            else:
                self.say("Цель покинула помещение.")
        else:
            self.play_sound("warning")
            self.say("В комнате нет сестры.")
    
    def borrow_item(self, person_id, item_name):
        if item_name not in self.items_db:
            self.say(f"Предмет '{item_name}' не найден в базе.")
            return False
        
        item = self.items_db[item_name]
        
        if item["borrowed_by"] is not None:
            self.play_sound("warning")
            self.say(f"{item_name} уже взял {item['borrowed_by']}.")
            return False
        
        item["borrowed_by"] = person_id
        item["borrow_date"] = datetime.now().isoformat()
        item["borrow_count"] += 1
        
        rule = self.get_person_rule(person_id)
        person_name = rule.get("name", person_id)
        
        self.log_event(f"📦 {person_name} взял {item_name}")
        self.stats["items_borrowed"] += 1
        
        self.say(f"{item_name} лежит {item['location']}. Не забудь вернуть.")
        return True
    
    def return_item(self, person_id, item_name):
        if item_name not in self.items_db:
            self.say(f"Предмет '{item_name}' не найден.")
            return False
        
        item = self.items_db[item_name]
        
        if item["borrowed_by"] != person_id:
            self.play_sound("warning")
            self.say(f"Этот предмет брал не ты.")
            return False
        
        item["borrowed_by"] = None
        item["borrow_date"] = None
        item["return_count"] += 1
        
        rule = self.get_person_rule(person_id)
        person_name = rule.get("name", person_id)
        
        self.log_event(f"✅ {person_name} вернул {item_name}")
        self.stats["items_returned"] += 1
        
        self.say(f"Спасибо, {person_name}. {item_name} на месте.")
        return True
    
    def check_debts(self):
        self.log_event("🔍 Проверка должников...")
        
        for item_name, item in self.items_db.items():
            if item["borrowed_by"] is not None:
                borrower = item["borrowed_by"]
                borrow_date = datetime.fromisoformat(item["borrow_date"])
                days_borrowed = (datetime.now() - borrow_date).days
                
                rule = self.get_person_rule(borrower)
                person_name = rule.get("name", borrower)
                
                if days_borrowed == Config.DEBT_REMINDER_DAYS:
                    self.say(f"{person_name}, напоминаю: ты взял {item_name} {days_borrowed} дней назад.")
                    self.stats["debt_reminders"] += 1
                elif days_borrowed == Config.DEBT_WARNING_DAYS:
                    self.say(f"{person_name}, при следующем входе напомни про {item_name}.")
                elif days_borrowed == Config.DEBT_REPORT_DAYS:
                    self.send_to_rico(f"{person_name} не вернул {item_name} уже {days_borrowed} дней!")
                elif days_borrowed >= Config.DEBT_PARENTS_DAYS:
                    self.send_to_parents(f"{person_name} не вернул {item_name} {days_borrowed} дней!")
    
    def test_sound(self):
        print("🔊 Тестирование звука...")
        self.play_sound("aiming")
        print("✅ Звук проигран")
    
    def test_full_protocol(self):
        print("🔊 Полный тест протокола...")
        self.play_sound("aiming")
        self.say("Тестовое предупреждение. Это не настоящая тревога.")
        time.sleep(2.5)
        self.play_sound("fire")
        self.say("Тестовый залп выполнен.")
        print("✅ Тест завершён")
    
    def log_event(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)
        
        if len(self.logs) >= 100:
            self.save_logs()
    
    def save_logs(self):
        with open(Config.LOG_FILE, 'a', encoding='utf-8') as f:
            for log in self.logs:
                f.write(log + "\n")
        self.logs = []
    
    def save_all_data(self):
        with open(Config.FAMILY_RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.family_rules, f, indent=2, ensure_ascii=False)
        
        with open(Config.ITEMS_DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.items_db, f, indent=2, ensure_ascii=False)
        
        with open(Config.STATISTICS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        
        self.save_logs()
        print("✅ Все данные сохранены")
    
    def play_sound(self, sound_name):
        if not SOUND_AVAILABLE:
            print(f"🔊 [ТЕКСТ] {sound_name}")
            return
        
        sounds = {
            "aiming": "vzhik.wav",
            "fire": "fire.wav",
            "warning": "warning.wav"
        }
        
        filename = sounds.get(sound_name)
        
        if filename and os.path.exists(filename):
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
                sound = pygame.mixer.Sound(filename)
                sound.play()
                print(f"🔊 Воспроизводится: {filename}")
                pygame.time.wait(int(sound.get_length() * 1000))
            except Exception as e:
                print(f"❌ Ошибка воспроизведения: {e}")
        else:
            print(f"⚠️ Файл {filename} не найден")
    
    def say(self, message):
        print(f"🗣️ СИСТЕМА: {message}")
        self.log_event(f"SAY: {message}")
    
    def send_to_rico(self, message):
        print(f"📱 СООБЩЕНИЕ РИКО: {message}")
        self.log_event(f"RICO_MSG: {message}")
    
    def send_to_parents(self, message):
        print(f"👪 РОДИТЕЛЯМ: {message}")
        self.log_event(f"PARENTS_MSG: {message}")
    
    def show_status(self):
        print("\n" + "="*60)
        print(f"🤖 СИСТЕМА {self.name.upper()} И ЕГО ТУРЕЛИ")
        print("="*60)
        
        print(f"\n📊 СТАТИСТИКА:")
        print(f"  Всего входов: {self.stats['total_entries']}")
        print(f"  Выстрелов нерфами: {self.stats['total_nerf_shots']}")
        print(f"  Изгнаний: {self.stats['expel_count']}")
        print(f"  Предметов взято: {self.stats['items_borrowed']}")
        print(f"  Предметов возвращено: {self.stats['items_returned']}")
        print(f"  Напоминаний о долгах: {self.stats['debt_reminders']}")
        
        print(f"\n👥 ЛЮДИ В ЗОНЕ:")
        if self.people_in_zone:
            for pid, data in self.people_in_zone.items():
                rule = self.get_person_rule(pid)
                print(f"  {rule.get('name', pid)} (с {time.time()-data['entered_at']:.0f} сек)")
        else:
            print("  Никого")
        
        print(f"\n🔫 ТУРЕЛИ:")
        for name, turret in self.turrets.items():
            print(f"  {name}: {turret['mode'].value}, патронов: {turret['ammo']}, {turret['position']}")
        
        print(f"\n📦 ПРЕДМЕТЫ В ДОЛГ:")
        found = False
        for item_name, item in self.items_db.items():
            if item["borrowed_by"] is not None:
                found = True
                rule = self.get_person_rule(item["borrowed_by"])
                person_name = rule.get('name', item["borrowed_by"])
                days = (datetime.now() - datetime.fromisoformat(item["borrow_date"])).days
                print(f"  {item_name} - у {person_name} ({days} дн.)")
        if not found:
            print("  Все предметы на месте")
        
        print("\n" + "="*60)
    
    def show_family_rules(self):
        print("\n" + "="*60)
        print("📜 СЕМЕЙНЫЙ КОДЕКС")
        print("="*60)
        
        for pid, rule in self.family_rules.items():
            print(f"\n👤 {rule.get('name', pid)} ({rule.get('type', 'unknown')}):")
            print(f"  Стук обязателен: {'да' if rule.get('knock_required') else 'нет'}")
            print(f"  Время на выход (кнопка): {rule.get('warning_time', 0)} сек")
            print(f"  Нерфы: {'да' if rule.get('nerfs') else 'нет'}")
            print(f"  Описание: {rule.get('description', '-')}")
        
        print("\n" + "="*60)
    
    def show_help(self):
        print("\n" + "="*60)
        print("📚 ДОСТУПНЫЕ КОМАНДЫ")
        print("="*60)
        print("  статус     - состояние системы")
        print("  правила    - семейный кодекс")
        print("  предметы   - список предметов")
        print("  прогнать   - активировать кнопку ПРОГНАТЬ")
        print("  тест звук  - проверить звук ВЖЖЖИК")
        print("  тест всё   - полный тест протокола (без сестры)")
        print("  тест варнинг - проверить звук предупреждения")
        print("  угол [0-180] - установить угол сервопривода")
        print("  тест серво   - автотест (0° → 90° → 180° → 90°)")
        print("  точный [угол] - установить и держать")
        print("  точный [угол] [сек] - установить на N сек, потом возврат в 90°")
        print("  вход       - симуляция входа (с камеры)")
        print("  вход [кто] [стук] - ручная симуляция")
        print("  взять [предмет]    - взять предмет")
        print("  вернуть [предмет]  - вернуть предмет")
        print("  долги      - проверить должников")
        print("  камера вкл - включить камеру")
        print("  камера выкл - выключить камеру")
        print("  сохранить  - сохранить все данные")
        print("  выход      - завершение")
        print("="*60)
    
    def show_items(self):
        print("\n" + "="*60)
        print("📦 БАЗА ПРЕДМЕТОВ")
        print("="*60)
        
        for item_name, item in self.items_db.items():
            status = f"у {self.get_person_rule(item['borrowed_by'])['name']}" if item["borrowed_by"] else "на месте"
            print(f"\n🔧 {item_name}:")
            print(f"  Где лежит: {item['location']}")
            print(f"  Описание: {item['description']}")
            print(f"  Статус: {status}")
            print(f"  Брали: {item['borrow_count']} раз")
        
        print("\n" + "="*60)
    
    def simulate_entry(self, person_id, knocked):
        if person_id in self.family_rules:
            self.person_at_door(person_id, knocked)
        else:
            print(f"❌ Неизвестный человек: {person_id}")
    
    def run(self):
        print("\nДобро пожаловать в систему управления мастерской Рико!")
        print("Введите 'help' для списка команд.\n")
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == "выход":
                    if self.camera:
                        self.camera.release()
                    self.save_all_data()
                    print("Система завершает работу. Все данные сохранены.")
                    break
                
                elif cmd == "help":
                    self.show_help()
                
                elif cmd == "статус":
                    self.show_status()
                
                elif cmd == "правила":
                    self.show_family_rules()
                
                elif cmd == "предметы":
                    self.show_items()
                
                elif cmd == "прогнать":
                    self.expel_button_pressed()
                
                elif cmd == "тест звук":
                    self.test_sound()
                
                elif cmd == "тест всё":
                    self.test_full_protocol()
                
                elif cmd == "тест варнинг":
                    print("🔊 Тестирование предупреждения...")
                    self.play_sound("warning")
                    print("✅ Предупреждение проиграно")
                
                elif cmd == "тест серво":
                    self.test_servo()
                
                elif cmd.startswith("угол "):
                    parts = cmd.split()
                    if len(parts) == 2:
                        self.set_servo_angle(parts[1])
                    else:
                        print("Использование: угол [0-180]")
                
                elif cmd.startswith("точный "):
                    parts = cmd.split()
                    if len(parts) == 2:
                        self.precise_angle(parts[1])
                    elif len(parts) == 3:
                        try:
                            self.precise_angle(parts[1], float(parts[2]))
                        except:
                            print("⚠️ Неверный формат. Используй: точный [угол] [секунды]")
                    else:
                        print("Использование: точный [угол] или точный [угол] [секунды]")
                
                elif cmd == "долги":
                    self.check_debts()
                
                elif cmd == "сохранить":
                    self.save_all_data()
                    print("✅ Данные сохранены")
                
                elif cmd == "камера вкл":
                    self.use_camera = True
                    if self.camera is None and FACE_RECOGNITION_AVAILABLE:
                        self.camera = cv2.VideoCapture(0)
                    print("✅ Камера включена")
                
                elif cmd == "камера выкл":
                    self.use_camera = False
                    if self.camera:
                        self.camera.release()
                        self.camera = None
                    print("✅ Камера выключена")
                
                elif cmd == "вход":
                    person_id = self.identify_person()
                    if person_id:
                        self.person_at_door(person_id, knocked=True)
                    else:
                        print("❌ Лицо не распознано")
                
                elif cmd.startswith("вход "):
                    parts = cmd.split()
                    if len(parts) >= 2:
                        person = parts[1]
                        knocked = len(parts) > 2 and parts[2] == "стук"
                        self.simulate_entry(person, knocked)
                
                elif cmd.startswith("взять "):
                    item = cmd[6:].strip()
                    self.borrow_item("sister", item)
                
                elif cmd.startswith("вернуть "):
                    item = cmd[8:].strip()
                    self.return_item("sister", item)
                
                else:
                    print("Неизвестная команда. Введите 'help'")
            
            except KeyboardInterrupt:
                print("\n\nПолучен сигнал прерывания...")
                if self.camera:
                    self.camera.release()
                self.save_all_data()
                break
            
            except Exception as e:
                print(f"❌ Ошибка: {e}")


# ====================== ЗАПУСК ======================

if __name__ == "__main__":
    system = RicoTurretSystem(name="Рико", use_camera=False)
    system.run()
