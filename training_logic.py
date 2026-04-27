import random
from typing import List, Dict

# Доступные упражнения
EXERCISES = {
    "pullups": "Подтягивания (турник)",
    "dips": "Отжимания на брусьях",
    "squats": "Приседания со своим весом",
    "pushups": "Отжимания от пола",
    "bench_press": "Жим штанги 25 кг лёжа",
    "bent_over_row": "Тяга штанги 25 кг в наклоне",
    "deadlift": "Становая тяга 25 кг",
    "lunges": "Выпады",
    "plank": "Планка (сек)",
    "leg_raises": "Подъёмы ног в висе"
}

def generate_program(level: str, goal: str) -> List[Dict]:
    """Возвращает список упражнений с количеством подходов и целевыми повторениями"""
    program = []
    if goal == "mass":
        # массонабор: 3-4 подхода по 8-12 повторений
        if level == "beginner":
            exercises = ["pushups", "squats", "dips", "pullups"]  # облегчённые варианты
            sets = 3
            reps = "8-10"
        elif level == "intermediate":
            exercises = ["pushups", "squats", "dips", "pullups", "bench_press", "bent_over_row"]
            sets = 4
            reps = "10-12"
        else:
            exercises = ["pullups", "dips", "squats", "bench_press", "deadlift", "bent_over_row"]
            sets = 4
            reps = "12-15"
    else:  # functional
        # функционал: больше повторений, меньше отдых
        if level == "beginner":
            exercises = ["pushups", "squats", "leg_raises", "plank"]
            sets = 3
            reps = "12-15"
        elif level == "intermediate":
            exercises = ["pullups", "dips", "squats", "pushups", "lunges", "plank"]
            sets = 3
            reps = "15-20"
        else:
            exercises = ["pullups", "dips", "squats", "deadlift", "lunges", "plank"]
            sets = 4
            reps = "20-25"
    
    for ex in exercises:
        program.append({
            "name": EXERCISES[ex],
            "key": ex,
            "sets": sets,
            "target_reps_range": reps,   # сохраняем как строку, при показе разбираем
            "target_reps_low": int(reps.split("-")[0]),
            "target_reps_high": int(reps.split("-")[1]),
            "current_target": int(reps.split("-")[0])  # старт с нижней границы
        })
    return program

def update_progress(old_program: List[Dict], user_results: Dict) -> List[Dict]:
    """
    user_results: { "exercise_key": [ [reps_set1], [reps_set2], ... ] }
    Увеличиваем target_reps, если пользователь стабильно превышает цель
    """
    new_program = []
    for ex in old_program:
        key = ex["key"]
        if key in user_results:
            all_reps = user_results[key]  # список списков (по подходам)
            # усредняем результаты всех подходов
            avg_reps = sum([sum(sub) for sub in all_reps]) / sum([len(sub) for sub in all_reps])
            # если среднее >= текущей цели + 2, увеличиваем цель на 1 (но не выше high)
            if avg_reps >= ex["current_target"] + 2 and ex["current_target"] < ex["target_reps_high"]:
                ex["current_target"] = min(ex["current_target"] + 1, ex["target_reps_high"])
            # если ниже цели -1, уменьшаем (но не ниже low)
            elif avg_reps < ex["current_target"] - 1 and ex["current_target"] > ex["target_reps_low"]:
                ex["current_target"] = max(ex["current_target"] - 1, ex["target_reps_low"])
        new_program.append(ex)
    return new_program