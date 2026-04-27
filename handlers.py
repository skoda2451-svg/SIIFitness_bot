import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from db import async_session
from models import User, Workout
from training_logic import generate_program, update_progress

# Состояния для ConversationHandler (тест)
AGE, WEIGHT, HEIGHT, LEVEL, GOAL = range(5)

# Состояние для тренировки
TRAINING = 100

# Клавиатуры
main_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("🏋️ Начать тренировку"), KeyboardButton("📊 Мой прогресс"), KeyboardButton("🔄 Сбросить тест")]],
    resize_keyboard=True
)

training_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("❌ Завершить тренировку")]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with async_session() as session:
        db_user = await session.get(User, user_id)
        if not db_user:
            # Новый пользователь – начинаем тест
            await update.message.reply_text(
                "Привет! Я твой виртуальный фитнес тренер.\n"
                "Я помогу тебе с тренировками, подберу программу и нагрузку.\n\n"
                "Давай познакомимся поближе. Для начала — сколько тебе лет?",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
            )
            return AGE
        else:
            await update.message.reply_text(
                f"С возвращением, {db_user.first_name}! Твоя программа готова.\n"
                "Жми 'Начать тренировку'.",
                reply_markup=main_keyboard
            )
            return ConversationHandler.END
    return AGE   # для нового пользователя

async def cancel_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тест отменён. Напиши /start, чтобы начать заново.")
    return ConversationHandler.END

async def age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        context.user_data["age"] = age
        await update.message.reply_text("Твой вес (кг)?")
        return WEIGHT
    except:
        await update.message.reply_text("Пожалуйста, введи число (только цифры).")
        return AGE

async def weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        context.user_data["weight"] = weight
        await update.message.reply_text("Твой рост (см)?")
        return HEIGHT
    except:
        await update.message.reply_text("Введи вес числом (например, 75.5).")
        return WEIGHT

async def height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text)
        context.user_data["height"] = height
        kb = ReplyKeyboardMarkup([["Новичок", "Средний"], ["Продвинутый"]], resize_keyboard=True)
        await update.message.reply_text("Твой уровень подготовки:", reply_markup=kb)
        return LEVEL
    except:
        await update.message.reply_text("Введи рост целым числом.")
        return HEIGHT

async def level_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    level_map = {"новичок": "beginner", "средний": "intermediate", "продвинутый": "advanced"}
    level_ru = update.message.text.lower()
    if level_ru not in level_map:
        await update.message.reply_text("Выбери из предложенных вариантов кнопкой.")
        return LEVEL
    context.user_data["level"] = level_map[level_ru]
    kb = ReplyKeyboardMarkup([["Масса", "Функционал"]], resize_keyboard=True)
    await update.message.reply_text("Какая у тебя цель?", reply_markup=kb)
    return GOAL

async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_map = {"масса": "mass", "функционал": "functional"}
    goal_ru = update.message.text.lower()
    if goal_ru not in goal_map:
        await update.message.reply_text("Выбери 'Масса' или 'Функционал'.")
        return GOAL
    context.user_data["goal"] = goal_map[goal_ru]
    
    # Генерируем программу
    program = generate_program(context.user_data["level"], context.user_data["goal"])
    
    # Сохраняем пользователя в БД
    async with async_session() as session:
        user = User(
            tg_id=update.effective_user.id,
            first_name=update.effective_user.first_name,
            age=context.user_data["age"],
            weight=context.user_data["weight"],
            height=context.user_data["height"],
            level=context.user_data["level"],
            goal=context.user_data["goal"],
            program=program
        )
        session.add(user)
        await session.commit()
        context.user_data["user_id"] = user.id
    
    # Отправляем программу
    msg = "✅ Программа составлена! Вот твои упражнения:\n\n"
    for idx, ex in enumerate(program, 1):
        msg += f"{idx}. {ex['name']} – {ex['sets']} подхода по {ex['target_reps_range']} повторений\n"
    msg += "\nТеперь нажимай 'Начать тренировку'."
    await update.message.reply_text(msg, reply_markup=main_keyboard)
    return ConversationHandler.END

# ---------- Обработчики тренировки ----------
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Начать тренировку'"""
    user_id = update.effective_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            await update.message.reply_text("Сначала пройди тест: /start")
            return
        if not user.program:
            await update.message.reply_text("Программа не найдена. Напиши /start")
            return
        
        # Инициализируем состояние тренировки в context.user_data
        context.user_data["training"] = {
            "program": user.program.copy(),
            "current_ex_index": 0,
            "current_set": 0,
            "results": {},      # { "exercise_key": [ [rep1, rep2,...], ...] }
            "total_exercises": len(user.program),
            "start_time": datetime.utcnow().isoformat()
        }
        # Показываем первое упражнение
        await show_current_exercise(update, context)
        return TRAINING

async def show_current_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    training = context.user_data["training"]
    ex_idx = training["current_ex_index"]
    if ex_idx >= training["total_exercises"]:
        await finish_training(update, context)
        return
    
    ex = training["program"][ex_idx]
    set_num = training["current_set"] + 1   # 1-индексация
    target = ex["current_target"]
    await update.message.reply_text(
        f"🏋️ {ex['name']}\n\nПодход {set_num} из {ex['sets']}\n"
        f"📌 Цель: {target} повторений\n\nВведи количество повторений, которое сделал:",
        reply_markup=training_keyboard
    )

async def handle_training_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь ввел результат подхода или нажал 'Завершить'"""
    text = update.message.text
    if text == "❌ Завершить тренировку":
        await finish_training(update, context)
        return
    
    training = context.user_data.get("training")
    if not training:
        await update.message.reply_text("Сначала нажми 'Начать тренировку'.")
        return
    
    # Парсим количество повторений
    try:
        reps = int(text)
    except:
        await update.message.reply_text("Введи число повторений.")
        return
    
    ex_idx = training["current_ex_index"]
    ex = training["program"][ex_idx]
    set_idx = training["current_set"]
    ex_key = ex["key"]
    
    # Сохраняем результат
    if ex_key not in training["results"]:
        training["results"][ex_key] = []
    # Убедимся, что список подходов соответствует текущему номеру
    while len(training["results"][ex_key]) <= set_idx:
        training["results"][ex_key].append([])
    training["results"][ex_key][set_idx] = [reps]
    
    # Переход к следующему подходу или упражнению
    if set_idx + 1 < ex["sets"]:
        training["current_set"] += 1
        await show_current_exercise(update, context)
    else:
        # Переход к следующему упражнению
        training["current_ex_index"] += 1
        training["current_set"] = 0
        if training["current_ex_index"] < training["total_exercises"]:
            await show_current_exercise(update, context)
        else:
            await finish_training(update, context)

async def finish_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает тренировку, считает прогресс и корректирует программу"""
    training = context.user_data.get("training")
    if not training:
        await update.message.reply_text("Нет активной тренировки.", reply_markup=main_keyboard)
        return
    
    # Подсчёт результатов
    results = training["results"]
    # Обновляем программу пользователя в БД
    async with async_session() as session:
        user = await session.get(User, update.effective_user.id)
        old_program = user.program
        # Используем функцию прогрессии
        new_program = update_progress(old_program, results)
        user.program = new_program
        
        # Сохраняем завершённую тренировку
        workout = Workout(
            user_id=user.id,
            exercises_data=results,
            completed=1
        )
        session.add(workout)
        await session.commit()
        
        # Формируем отчёт
        total_reps = sum(sum(vals[0]) for ex_res in results.values() for vals in ex_res)
        report = f"✅ Тренировка завершена!\n\n"
        report += f"📊 Всего повторений: {total_reps}\n"
        report += "🎯 Корректировки программы учтены на следующую тренировку.\n\n"
        report += "Продолжай в том же духе! Нажимай 'Начать тренировку' снова."
        await update.message.reply_text(report, reply_markup=main_keyboard)
    
    # Очищаем состояние
    context.user_data.pop("training", None)

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Мой прогресс' - показывает последние 3 тренировки"""
    user_id = update.effective_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.workouts:
            await update.message.reply_text("У вас пока нет завершённых тренировок.")
            return
        workouts = sorted(user.workouts, key=lambda w: w.date, reverse=True)[:3]
        msg = "📈 Последние тренировки:\n\n"
        for w in workouts:
            total_reps = sum(sum(vals[0]) for ex_res in w.exercises_data.values() for vals in ex_res)
            msg += f"🗓 {w.date.strftime('%d.%m.%Y %H:%M')} – {total_reps} повторений\n"
        await update.message.reply_text(msg, reply_markup=main_keyboard)

async def reset_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс данных пользователя и повторный тест"""
    user_id = update.effective_user.id
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
            await session.commit()
    await update.message.reply_text("Данные сброшены. Напиши /start, чтобы пройти тест заново.")