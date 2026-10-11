import sqlite3
import random
from datetime import datetime
import sys
import os
import shutil

def get_connection():
    if getattr(sys, 'frozen', False):
        # Desktop verzia (PyInstaller)
        from kivy.app import App
        app = App.get_running_app()
        if app is None:
            raise RuntimeError("Databáza aplikácie vyžaduje spustenú Kivy aplikáciu.")

        os.makedirs(app.user_data_dir, exist_ok=True)
        target_db = os.path.join(app.user_data_dir, 'questions.db')
        if not os.path.exists(target_db):
            source_db = os.path.join(sys._MEIPASS, 'questions.db')
            if os.path.exists(source_db):
                shutil.copy(source_db, target_db)
    else:
        # Vývojový režim / Android
        try:
            from kivy.app import App
            user_data = App.get_running_app().user_data_dir
            if not os.path.exists(user_data):
                os.makedirs(user_data)
            target_db = os.path.join(user_data, 'questions.db')

            if not os.path.exists(target_db):
                from kivy.resources import resource_find
                source_db = resource_find('questions.db')
                if source_db:
                    shutil.copy(source_db, target_db)
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
            target_db = os.path.join(base_path, 'questions.db')

    return sqlite3.connect(target_db)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question_text TEXT NOT NULL,
            image_path TEXT,
            image_blob BLOB,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            correct_answer INTEGER NOT NULL, 
            points INTEGER NOT NULL,         
            learning_status INTEGER DEFAULT 0,
            difficulty INTEGER DEFAULT 1,      
            streak INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            earned_points INTEGER NOT NULL,
            total_points INTEGER NOT NULL,
            percentage REAL NOT NULL,
            is_successful INTEGER NOT NULL,
            duration_seconds INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_stats (
            category TEXT PRIMARY KEY,
            total_answered INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            earned_points INTEGER DEFAULT 0,
            total_points INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute("PRAGMA table_info(questions)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'difficulty' not in columns:
        cursor.execute("ALTER TABLE questions ADD COLUMN difficulty INTEGER DEFAULT 1")

    conn.commit()
    conn.close()

def add_question(category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO questions (category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status))
    conn.commit()
    conn.close()

def update_question(q_id, category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status):
    conn = get_connection()
    cursor = conn.cursor()
    if image_blob is not None:
        cursor.execute('''
            UPDATE questions 
            SET category = ?, question_text = ?, image_path = ?, image_blob = ?, option_a = ?, option_b = ?, option_c = ?, correct_answer = ?, points = ?, learning_status = ?
            WHERE id = ?
        ''', (category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, q_id))
    else:
        cursor.execute('''
            UPDATE questions 
            SET category = ?, question_text = ?, image_path = ?, option_a = ?, option_b = ?, option_c = ?, correct_answer = ?, points = ?, learning_status = ?
            WHERE id = ?
        ''', (category, question_text, image_path, option_a, option_b, option_c, correct_answer, points, learning_status, q_id))
    conn.commit()
    conn.close()

def delete_question(q_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (q_id,))
    conn.commit()
    conn.close()

def reset_question_stats(q_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE questions 
        SET difficulty = 1, learning_status = 0, streak = 0, total_attempts = 0, total_correct = 0
        WHERE id = ?
    ''', (q_id,))
    conn.commit()
    conn.close()

def clear_all_statistics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_history")
    cursor.execute("DELETE FROM category_stats")
    conn.commit()
    conn.close()

def get_question_counts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category")
    rows = cursor.fetchall()
    cat_counts = {row[0]: row[1] for row in rows}
    conn.close()
    return total, cat_counts

def get_question_ids(category=None, search_query=None, status_filter=None, sort_by=None):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT id FROM questions WHERE 1=1"
    params = []
    if category and category != "Všetky kategórie":
        query += " AND category = ?"
        params.append(category)
    if search_query:
        query += " AND question_text LIKE ?"
        params.append(f"%{search_query}%")
    if status_filter is not None:
        query += " AND learning_status = ?"
        params.append(status_filter)
    if sort_by == "Najťažšie prvé":
        query += " ORDER BY difficulty DESC, id DESC"
    elif sort_by == "Najľahšie prvé":
        query += " ORDER BY difficulty ASC, id ASC"
    else:
        query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def find_duplicate_questions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, question_text, option_a, option_b, option_c, correct_answer FROM questions ORDER BY id")
    questions = cursor.fetchall()
    conn.close()
    
    duplicates = []
    grouped_questions = {}

    for question in questions:
        q_id, category, text, option_a, option_b, option_c, correct_answer = question
        options = (option_a, option_b, option_c)
        correct_text = options[correct_answer].strip().lower() if 0 <= correct_answer < 3 else ""
        key = (text.strip().lower(), correct_text)
        matching_questions = grouped_questions.setdefault(key, [])
        for previous in matching_questions:
            duplicates.append((previous[0], previous[1], previous[2], q_id, category, text))
        matching_questions.append(question)

    duplicates.sort(key=lambda duplicate: (duplicate[0], duplicate[3]))
    return duplicates

def get_questions(category=None, search_query=None, status_filter=None, sort_by=None, limit=None, offset=0):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT id, category, question_text, points, learning_status, difficulty FROM questions WHERE 1=1"
    params = []
    
    if category and category != "Všetky kategórie":
        query += " AND category = ?"
        params.append(category)
        
    if search_query:
        query += " AND question_text LIKE ?"
        params.append(f"%{search_query}%")

    if status_filter is not None:
        query += " AND learning_status = ?"
        params.append(status_filter)

    if sort_by == "Najťažšie prvé":
        query += " ORDER BY difficulty DESC, id DESC"
    elif sort_by == "Najľahšie prvé":
        query += " ORDER BY difficulty ASC, id ASC"
    else:
        query += " ORDER BY id DESC"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend((limit, offset))
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_question_by_id(q_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, difficulty 
        FROM questions WHERE id = ?
    ''', (q_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_question_after_test(q_id, is_correct):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT learning_status, difficulty, total_attempts, total_correct, streak FROM questions WHERE id = ?", (q_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
        
    learning_status, difficulty, attempts, correct, streak = row
    attempts += 1
    
    if is_correct:
        correct += 1
        streak += 1
        if streak >= 2 and difficulty > 1:
            difficulty -= 1
        
        if learning_status == 0 or learning_status == 1:
            learning_status = 2
        elif learning_status == 2:
            learning_status = 3
    else:
        streak = 0
        if difficulty < 5:
            difficulty += 1
            
        if learning_status == 3:
            learning_status = 2
        else:
            learning_status = 1
            
    cursor.execute('''
        UPDATE questions 
        SET learning_status = ?, difficulty = ?, total_attempts = ?, total_correct = ?, streak = ?
        WHERE id = ?
    ''', (learning_status, difficulty, attempts, correct, streak, q_id))
    conn.commit()
    conn.close()

def save_test_result(earned_points, total_points, duration_seconds, category_results):
    conn = get_connection()
    cursor = conn.cursor()
    
    percentage = (earned_points / total_points * 100) if total_points > 0 else 0
    is_successful = 1 if percentage >= 90 else 0
    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    cursor.execute('''
        INSERT INTO test_history (date, earned_points, total_points, percentage, is_successful, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (date_str, earned_points, total_points, percentage, is_successful, duration_seconds))
    
    for cat, data in category_results.items():
        cursor.execute('''
            INSERT INTO category_stats (category, total_answered, total_correct, earned_points, total_points)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category) DO UPDATE SET
                total_answered = total_answered + ?,
                total_correct = total_correct + ?,
                earned_points = earned_points + ?,
                total_points = total_points + ?
        ''', (cat, data['total'], data['correct'], data['earned_pts'], data['total_pts'],
              data['total'], data['correct'], data['earned_pts'], data['total_pts']))
        
    conn.commit()
    conn.close()

def get_overall_stats():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*), SUM(is_successful), AVG(percentage) FROM test_history")
    res = cursor.fetchone()
    total_tests = res[0] if res[0] else 0
    successful_tests = res[1] if res[1] else 0
    avg_percentage = res[2] if res[2] else 0.0
    
    cursor.execute("SELECT category, total_answered, total_correct, earned_points, total_points FROM category_stats")
    cat_rows = cursor.fetchall()
    
    conn.close()
    return total_tests, successful_tests, avg_percentage, cat_rows

def get_problematic_categories(limit=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, 
               CASE WHEN total_points > 0 THEN (CAST(earned_points AS REAL) / total_points) * 100 ELSE 0 END as pct
        FROM category_stats
        ORDER BY pct ASC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def generate_test_questions(mode="Cielený (Smart)", category="Všetky kategórie", limit=40):
    conn = get_connection()
    cursor = conn.cursor()
    
    category_quotas = [
        ("Pravidlá cestnej premávky", 8),
        ("Uplatňovanie pravidiel prednosti v jazde a rýchlostné obmedzenia", 2),
        ("Dopravné značky a dopravné zariadenia", 8),
        ("Dopravné situácie na križovatkách", 4),
        ("Všeobecné pravidlá správania sa v prípade dopravnej nehody", 1),
        ("Teória vedenia vozidla", 3),
        ("Predpisy týkajúce sa dokladov požadovaných v prípade používania vozidla a organizácia času v doprave", 2),
        ("Podmienky prevádzky vozidiel v premávke na pozemnych komunikáciách", 2),
        ("Zásady bezpečnej jazdy", 8),
        ("Konštrukcia vozidiel a ich údržba", 2)  # Opravené z 1 na 2 (spolu presne 40 otázok)
    ]
    
    final_test_questions = []
    
    if category == "Problematické kategórie":
        prob_cats = get_problematic_categories(3)
        if not prob_cats:
            category = "Všetky kategórie"
        else:
            per_cat = 40 // len(prob_cats)
            for c_name in prob_cats:
                cursor.execute("""
                    SELECT id, category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, difficulty 
                    FROM questions WHERE category = ? ORDER BY learning_status ASC, RANDOM() LIMIT ?
                """, (c_name, per_cat))
                rows = cursor.fetchall()
                final_test_questions.extend(rows)
            random.shuffle(final_test_questions)
            conn.close()
            return _shuffle_question_options(final_test_questions)

    if category and category != "Všetky kategórie":
        quota = 40
        base_query = """
            SELECT id, category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, difficulty 
            FROM questions WHERE category = ?
        """
        params = [category]
        
        if mode == "Cielený (Smart)":
            base_query += " ORDER BY learning_status ASC, difficulty DESC, RANDOM() LIMIT ?"
        elif mode == "Prioritný (Nepoznané prvé)":
            base_query += " ORDER BY learning_status ASC, RANDOM() LIMIT ?"
        else:
            base_query += " ORDER BY RANDOM() LIMIT ?"
            
        params.append(quota)
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        
        if mode == "Prioritný (Nepoznané prvé)":
            rows.sort(key=lambda x: x[10])
            
        final_test_questions = rows
    else:
        for cat_name, count in category_quotas:
            base_query = """
                SELECT id, category, question_text, image_path, image_blob, option_a, option_b, option_c, correct_answer, points, learning_status, difficulty 
                FROM questions WHERE category = ?
            """
            params = [cat_name]
            
            if mode == "Cielený (Smart)":
                base_query += " ORDER BY learning_status ASC, difficulty DESC, RANDOM() LIMIT ?"
            elif mode == "Prioritný (Nepoznané prvé)":
                base_query += " ORDER BY learning_status ASC, RANDOM() LIMIT ?"
            else:
                base_query += " ORDER BY RANDOM() LIMIT ?"
                
            params.append(count)
            cursor.execute(base_query, params)
            cat_rows = cursor.fetchall()
            
            if mode == "Prioritný (Nepoznané prvé)":
                cat_rows.sort(key=lambda x: x[10])
                
            final_test_questions.extend(cat_rows)
            
    conn.close()
    return _shuffle_question_options(final_test_questions)

def _shuffle_question_options(questions_list):
    processed = []
    for q in questions_list:
        q_list = list(q)
        opt_a, opt_b, opt_c = q_list[5], q_list[6], q_list[7]
        corr_idx = q_list[8]
        
        options = [opt_a, opt_b, opt_c]
        if 0 <= corr_idx < 3:
            correct_text = options[corr_idx]
            indexed_options = list(enumerate(options))
            random.shuffle(indexed_options)
            
            new_opts = [item[1] for item in indexed_options]
            new_corr_idx = new_opts.index(correct_text)
            
            q_list[5] = new_opts[0]
            q_list[6] = new_opts[1]
            q_list[7] = new_opts[2]
            q_list[8] = new_corr_idx
            
        processed.append(tuple(q_list))
    return processed