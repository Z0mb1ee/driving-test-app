import os
import sys

# Must be set before importing Kivy.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "sdl2")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image as CoreImageWidget
from kivy.core.image import Image as CoreImage
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.utils import platform

import io
import subprocess
import time

import database

# Safe loading of quiz.kv for both PyInstaller and normal Python
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

kv_path = os.path.join(base_path, "quiz.kv")

CATEGORY_POINTS_MAP = {
    "Pravidlá cestnej premávky": 3,
    "Uplatňovanie pravidiel prednosti v jazde a rýchlostné obmedzenia": 3,
    "Dopravné značky a dopravné zariadenia": 2,
    "Dopravné situácie na križovatkách": 4,
    "Všeobecné pravidlá správania sa v prípade dopravnej nehody": 2,
    "Teória vedenia vozidla": 2,
    "Predpisy týkajúce sa dokladov požadovaných v prípade používania vozidla a organizácia času v doprave": 1,
    "Podmienky prevádzky vozidiel v premávke na pozemnych komunikáciách": 1,
    "Zásady bezpečnej jazdy": 3,
    "Konštrukcia vozidiel a ich údržba": 1
}


def blob_to_kivy_image(blob_data):
    if not blob_data:
        return None
    try:
        stream = io.BytesIO(blob_data)
        im = CoreImage(stream, ext="png")
        w = CoreImageWidget()
        w.texture = im.texture
        w.allow_stretch = True
        w.keep_ratio = True
        return w
    except Exception as e:
        print(f"Chyba pri vykresľovaní obrázka: {e}")
        return None


class MenuScreen(Screen):
    def go_to_test_settings(self):
        self.manager.current = "test_settings"

    def go_to_stats(self):
        stats_screen = self.manager.get_screen("stats")
        stats_screen.load_stats()
        self.manager.current = "stats"


class StatsScreen(Screen):
    def load_stats(self):
        total_tests, successful_tests, avg_percentage, cat_rows = database.get_overall_stats()

        failed_tests = total_tests - successful_tests
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0

        self.ids.stats_summary_label.text = (
            f"Celkový počet testov: {total_tests} | "
            f"Úspešné: {successful_tests} 🟢 | Neúspešné: {failed_tests} 🔴\n"
            f"Úspešnosť testov: {success_rate:.1f}% | Priemerné skóre: {avg_percentage:.1f}%"
        )

        container = self.ids.stats_categories_layout
        container.clear_widgets()

        for row in cat_rows:
            cat_name, answered, correct, earned_pts, total_pts = row
            pct = (earned_pts / total_pts * 100) if total_pts > 0 else 0

            box = BoxLayout(size_hint_y=None, height=40, spacing=10)
            lbl_name = Label(text=cat_name, size_hint_x=0.6, halign="left", text_size=(400, None), font_size=13)
            lbl_det = Label(text=f"Body: {earned_pts}/{total_pts}", size_hint_x=0.2, font_size=13)
            lbl_pct = Label(
                text=f"{pct:.1f}%",
                size_hint_x=0.2,
                color=(0.1, 0.6, 0.2, 1) if pct >= 80 else (0.8, 0.2, 0.2, 1),
                bold=True,
                font_size=13
            )

            box.add_widget(lbl_name)
            box.add_widget(lbl_det)
            box.add_widget(lbl_pct)
            container.add_widget(box)

    def clear_stats(self):
        database.clear_all_statistics()
        self.load_stats()


class AddQuestionScreen(Screen):
    pasted_image_bytes = None

    def on_category_changed(self, cat_name):
        pts = CATEGORY_POINTS_MAP.get(cat_name, 1)
        self.ids.points_label.text = f"Body: {pts} (automaticky)"

    def paste_image(self):
        try:
            p = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if p.returncode == 0 and p.stdout:
                self.pasted_image_bytes = p.stdout
                self.show_preview(self.pasted_image_bytes)
                self.ids.img_status_label.text = "Obrázok úspešne zachytený!"
                self.ids.img_status_label.color = (0, 1, 0, 1)
                return

            img_data = Clipboard.get("image/png")
            if img_data:
                self.pasted_image_bytes = img_data
                self.show_preview(self.pasted_image_bytes)
                self.ids.img_status_label.text = "Obrázok úspešne vložený!"
                self.ids.img_status_label.color = (0, 1, 0, 1)
            else:
                self.ids.img_status_label.text = "Schránka neobsahuje obrázok."
                self.ids.img_status_label.color = (1, 0, 0, 1)
        except Exception as e:
            self.ids.img_status_label.text = "Chyba pri čítaní schránky."
            print(e)

    def show_preview(self, blob_data):
        preview_container = self.ids.preview_container
        preview_container.clear_widgets()
        img_widget = blob_to_kivy_image(blob_data)
        if img_widget:
            preview_container.add_widget(img_widget)

    def save_question(self, cat_spinner, text_input, opt_a, opt_b, opt_c, correct_spinner, status_spinner):
        category = cat_spinner.text
        text = text_input.text
        a = opt_a.text
        b = opt_b.text
        c = opt_c.text

        correct_map = {"A": 0, "B": 1, "C": 2}
        correct = correct_map.get(correct_spinner.text, 0)

        status_map = {"Nepoznám": 0, "Neviem": 1, "Neistý": 2, "Viem": 3}
        learning_status = status_map.get(status_spinner.text, 0)

        points = CATEGORY_POINTS_MAP.get(category, 1)

        if not text or not a or not b or not c:
            print("Error: Vyplňte povinné polia!")
            return

        database.add_question(category, text, None, self.pasted_image_bytes, a, b, c, correct, points, learning_status)
        print("Otázka úspešne pridaná!")

        text_input.text = ""
        opt_a.text = ""
        opt_b.text = ""
        opt_c.text = ""
        self.pasted_image_bytes = None
        self.ids.preview_container.clear_widgets()
        self.ids.img_status_label.text = "Žiadny obrázok nie je vložený"
        self.ids.img_status_label.color = (0.7, 0.7, 0.7, 1)


class ViewQuestionsScreen(Screen):
    page_size = 40

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.search_event = None
        self.filter_values = {}
        self.filtered_ids = []
        self.duplicate_rows = []
        self.duplicate_mode = False
        self.loaded_count = 0
        self.total_count = 0
        self.load_more_button = None

    def on_enter(self):
        self.load_questions()

    def schedule_search(self):
        if self.search_event:
            self.search_event.cancel()
        self.search_event = Clock.schedule_once(lambda dt: self.load_questions(), 0.3)

    def load_questions(self):
        if self.search_event:
            self.search_event.cancel()
            self.search_event = None

        search_text = self.ids.search_box.text
        cat_text = self.ids.cat_filter.text
        status_text = self.ids.status_filter.text
        sort_text = self.ids.sort_filter.text

        status_map = {"Všetky statusy": None, "❓ Nepoznám": 0, "🔴 Neviem": 1, "🟡 Neistý": 2, "🟢 Viem": 3}
        status_val = status_map.get(status_text)

        self.duplicate_mode = False
        self.filter_values = {
            "category": cat_text,
            "search_query": search_text,
            "status_filter": status_val,
            "sort_by": sort_text,
        }
        self.filtered_ids = database.get_question_ids(**self.filter_values)
        self.total_count = len(self.filtered_ids)
        self.loaded_count = 0
        self.duplicate_rows = []
        self._render_question_page()

    def _clear_list(self):
        container = self.ids.questions_list_layout
        container.clear_widgets()
        self.load_more_button = None

    def _add_list_button(self, text, on_press, background_color=(0.22, 0.22, 0.22, 1)):
        btn = Button(
            text=text,
            size_hint_y=None,
            height=dp(72),
            font_size=sp(16),
            text_size=(Window.width - dp(56), None),
            padding=(dp(12), dp(10)),
            halign="left",
            valign="middle",
            background_color=background_color,
        )
        btn.bind(size=lambda widget, size: setattr(widget, "text_size", (size[0] - dp(24), None)))
        btn.bind(texture_size=lambda widget, size: setattr(widget, "height", max(dp(64), size[1] + dp(20))))
        btn.bind(on_press=on_press)
        self.ids.questions_list_layout.add_widget(btn)

    def _render_question_page(self):
        self._clear_list()
        status_text_map = {0: "❓ Nepoznám", 1: "🔴 Neviem", 2: "🟡 Neistý", 3: "🟢 Viem"}
        if not self.total_count:
            self.ids.count_label.text = "Nenašli sa žiadne otázky."
            self.ids.questions_list_layout.add_widget(Label(
                text="Žiadne otázky sa nenašli.",
                size_hint_y=None,
                height=dp(48),
                font_size=sp(16),
                color=(0.7, 0.7, 0.7, 1),
            ))
            return

        rows = database.get_questions(
            **self.filter_values,
            limit=self.page_size,
            offset=self.loaded_count,
        )
        self.loaded_count += len(rows)
        for q in rows:
            q_id, cat, q_text, points, learning_status, difficulty = q
            status_str = status_text_map.get(learning_status, "❓ Nepoznám")
            display_text = f"{status_str}  |  Obtiažnosť {difficulty}/5  |  {cat}  |  {points} b\n{q_text}"
            self._add_list_button(
                display_text,
                lambda instance, qid=q_id: self.open_question_preview(qid),
            )

        self.manager.get_screen("question_preview").current_filtered_ids = self.filtered_ids
        self.ids.count_label.text = f"Zobrazené: {self.loaded_count} / {self.total_count}"
        if self.loaded_count < self.total_count:
            self._add_load_more_button(self.total_count - self.loaded_count)

    def check_duplicates(self):
        if self.search_event:
            self.search_event.cancel()
            self.search_event = None
        self.duplicate_rows = database.find_duplicate_questions()
        self.duplicate_mode = True
        self.total_count = len(self.duplicate_rows)
        self.loaded_count = 0
        self.filtered_ids = list(dict.fromkeys(
            q_id for duplicate in self.duplicate_rows for q_id in (duplicate[0], duplicate[3])
        ))
        self._render_duplicate_page()

    def _render_duplicate_page(self):
        self._clear_list()
        self.manager.get_screen("question_preview").current_filtered_ids = self.filtered_ids
        if not self.total_count:
            self.ids.count_label.text = "Kontrola duplikátov: Všetko je čisté!"
            self.ids.questions_list_layout.add_widget(Label(
                text="Nenašli sa žiadne duplicitné otázky.",
                size_hint_y=None,
                height=dp(48),
                font_size=sp(16),
                color=(0, 1, 0, 1),
            ))
            return

        page = self.duplicate_rows[self.loaded_count:self.loaded_count + self.page_size]
        self.loaded_count += len(page)
        for d in page:
            id1, cat1, text1, id2, cat2, text2 = d
            display_text = f"DUPLIKÁT: ID {id1} ({cat1}) / ID {id2} ({cat2})\n{text1}"
            self._add_list_button(
                display_text,
                lambda instance, qid=id1: self.open_question_preview(qid),
                background_color=(0.65, 0.28, 0.16, 1),
            )

        self.ids.count_label.text = f"Duplikáty: {self.loaded_count} / {self.total_count}"
        if self.loaded_count < self.total_count:
            self._add_load_more_button(self.total_count - self.loaded_count)

    def _add_load_more_button(self, remaining):
        self.load_more_button = Button(
            text=f"Načítať ďalšie ({remaining})",
            size_hint_y=None,
            height=dp(52),
            font_size=sp(16),
        )
        self.load_more_button.bind(on_press=self.load_more)
        self.ids.questions_list_layout.add_widget(self.load_more_button)

    def load_more(self, *_args):
        if self.duplicate_mode:
            self._render_duplicate_page()
        else:
            self._render_question_page()

    def open_question_preview(self, q_id):
        preview_screen = self.manager.get_screen("question_preview")
        preview_screen.load_question(q_id)
        self.manager.current = "question_preview"


class QuestionPreviewScreen(Screen):
    current_q_id = None
    current_filtered_ids = []
    current_category_name = "Všetky kategórie"

    def load_question(self, q_id):
        self.current_q_id = q_id
        row = database.get_question_by_id(q_id)
        if not row:
            return

        _, cat, text, img_path, img_blob, opt_a, opt_b, opt_c, correct_idx, points, learning_status, difficulty = row
        self.current_category_name = cat

        status_text = {0: "Nepoznám", 1: "Neviem", 2: "Neistý", 3: "Viem"}.get(learning_status, "Nepoznám")
        self.ids.prev_header.text = f"{cat}  |  {points} b  |  Obtiažnosť {difficulty}/5  |  {status_text}"
        self.ids.prev_text.text = text

        btn_map = {0: self.ids.prev_opt_a, 1: self.ids.prev_opt_b, 2: self.ids.prev_opt_c}
        texts = {0: f"A) {opt_a}", 1: f"B) {opt_b}", 2: f"C) {opt_c}"}

        for idx, btn in btn_map.items():
            btn.text = texts[idx]
            if idx == correct_idx:
                btn.background_color = (0.2, 0.7, 0.3, 1)
            else:
                btn.background_color = (0.9, 0.9, 0.9, 1)

        container = self.ids.prev_image_container
        container.clear_widgets()
        if img_blob:
            img_w = blob_to_kivy_image(img_blob)
            if img_w:
                img_w.size_hint = (1, 1)
                container.add_widget(img_w)

    def next_question(self):
        if self.current_q_id in self.current_filtered_ids:
            idx = self.current_filtered_ids.index(self.current_q_id)
            if idx < len(self.current_filtered_ids) - 1:
                self.load_question(self.current_filtered_ids[idx + 1])

    def prev_question(self):
        if self.current_q_id in self.current_filtered_ids:
            idx = self.current_filtered_ids.index(self.current_q_id)
            if idx > 0:
                self.load_question(self.current_filtered_ids[idx - 1])

    def go_to_edit(self):
        edit_screen = self.manager.get_screen("edit_question")
        edit_screen.load_question_data(self.current_q_id, self.current_category_name)
        self.manager.current = "edit_question"

    def delete_this_question(self):
        if self.current_q_id:
            database.delete_question(self.current_q_id)
            self.manager.current = "view_questions"

    def reset_this_question(self):
        if self.current_q_id:
            database.reset_question_stats(self.current_q_id)
            self.load_question(self.current_q_id)


class EditQuestionScreen(Screen):
    current_q_id = None
    new_image_bytes = None
    edit_filtered_ids = []
    current_category_filter = None

    def on_category_changed(self, cat_name):
        pts = CATEGORY_POINTS_MAP.get(cat_name, 1)
        self.ids.edit_points_label.text = f"Body: {pts} (automaticky)"

    def load_question_data(self, q_id, category_filter="Všetky kategórie"):
        self.current_q_id = q_id
        self.new_image_bytes = None
        self.current_category_filter = category_filter
        self.edit_filtered_ids = database.get_question_ids(category_filter)

        row = database.get_question_by_id(q_id)
        if not row:
            return

        _, cat, text, img_path, img_blob, a, b, c, correct_idx, points, learning_status, difficulty = row

        self.ids.edit_cat_spinner.text = cat
        self.ids.edit_q_text.text = text
        self.ids.edit_opt_a.text = a
        self.ids.edit_opt_b.text = b
        self.ids.edit_opt_c.text = c

        reverse_map = {0: "A", 1: "B", 2: "C"}
        self.ids.edit_correct_spinner.text = reverse_map.get(correct_idx, "A")
        self.ids.edit_points_label.text = f"Body: {points} (automaticky)"

        status_reverse_map = {0: "Nepoznám", 1: "Neviem", 2: "Neistý", 3: "Viem"}
        self.ids.edit_status_spinner.text = status_reverse_map.get(learning_status, "Nepoznám")

        self.ids.edit_difficulty_label.text = f"Automatická obtiažnosť: {difficulty} / 5 (ID: {q_id})"

        preview_container = self.ids.edit_preview_container
        preview_container.clear_widgets()
        if img_blob:
            img_widget = blob_to_kivy_image(img_blob)
            if img_widget:
                preview_container.add_widget(img_widget)

    def paste_image(self):
        try:
            p = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if p.returncode == 0 and p.stdout:
                self.new_image_bytes = p.stdout
                self.show_preview(self.new_image_bytes)
                self.ids.edit_img_status.text = "Nový obrázok pripravený!"
                return

            img_data = Clipboard.get("image/png")
            if img_data:
                self.new_image_bytes = img_data
                self.show_preview(self.new_image_bytes)
                self.ids.edit_img_status.text = "Nový obrázok pripravený!"
        except Exception:
            self.ids.edit_img_status.text = "Chyba pri vkladaní obrázka."

    def show_preview(self, blob_data):
        preview_container = self.ids.edit_preview_container
        preview_container.clear_widgets()
        img_widget = blob_to_kivy_image(blob_data)
        if img_widget:
            preview_container.add_widget(img_widget)

    def save_changes(self):
        if not self.current_q_id:
            return

        category = self.ids.edit_cat_spinner.text
        text = self.ids.edit_q_text.text
        a = self.ids.edit_opt_a.text
        b = self.ids.edit_opt_b.text
        c = self.ids.edit_opt_c.text

        correct_map = {"A": 0, "B": 1, "C": 2}
        correct = correct_map.get(self.ids.edit_correct_spinner.text, 0)

        status_map = {"Nepoznám": 0, "Neviem": 1, "Neistý": 2, "Viem": 3}
        learning_status = status_map.get(self.ids.edit_status_spinner.text, 0)

        points = CATEGORY_POINTS_MAP.get(category, 1)

        database.update_question(
            self.current_q_id,
            category,
            text,
            None,
            self.new_image_bytes,
            a,
            b,
            c,
            correct,
            points,
            learning_status
        )

    def save_and_next(self):
        self.save_changes()
        if self.current_q_id in self.edit_filtered_ids:
            idx = self.edit_filtered_ids.index(self.current_q_id)
            if idx < len(self.edit_filtered_ids) - 1:
                next_id = self.edit_filtered_ids[idx + 1]
                self.load_question_data(next_id, self.current_category_filter)

    def next_question(self):
        if self.current_q_id in self.edit_filtered_ids:
            idx = self.edit_filtered_ids.index(self.current_q_id)
            if idx < len(self.edit_filtered_ids) - 1:
                next_id = self.edit_filtered_ids[idx + 1]
                self.load_question_data(next_id, self.current_category_filter)

    def prev_question(self):
        if self.current_q_id in self.edit_filtered_ids:
            idx = self.edit_filtered_ids.index(self.current_q_id)
            if idx > 0:
                prev_id = self.edit_filtered_ids[idx - 1]
                self.load_question_data(prev_id, self.current_category_filter)


class TestSettingsScreen(Screen):
    def start_configured_test(self, mode_spinner, category_spinner):
        selected_mode = mode_spinner.text
        selected_category = category_spinner.text

        test_questions = database.generate_test_questions(mode=selected_mode, category=selected_category, limit=40)

        if not test_questions:
            print("Chyba: V databáze nie sú žiadne otázky pre tento výber!")
            return

        active_test_screen = self.manager.get_screen("active_test")
        active_test_screen.load_test(test_questions)
        self.manager.current = "active_test"


class ActiveTestScreen(Screen):
    questions = []
    current_index = 0
    user_answers = {}
    time_left = 30 * 60
    start_timestamp = 0
    timer_event = None

    def load_test(self, questions_list):
        self.questions = questions_list
        self.current_index = 0
        self.user_answers = {}
        self.time_left = 30 * 60
        self.start_timestamp = time.time()

        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

        self.build_top_grid()
        self.display_current_question()

    def update_timer(self, dt):
        if self.time_left > 0:
            self.time_left -= 1
            minutes = self.time_left // 60
            seconds = self.time_left % 60
            self.ids.timer_label.text = f"Čas: {minutes:02d}:{seconds:02d}"
        else:
            self.timer_event.cancel()
            self.finish_test()

    def build_top_grid(self):
        grid = self.ids.top_questions_grid
        grid.clear_widgets()

        for i in range(len(self.questions)):
            btn = Button(
                text=str(i + 1),
                size_hint_y=None,
                height=dp(40),
                font_size=sp(15),
            )
            btn.bind(on_press=lambda instance, idx=i: self.jump_to_question(idx))
            grid.add_widget(btn)
        self.update_top_grid_colors()

    def update_top_grid_colors(self):
        grid = self.ids.top_questions_grid
        for i, btn in enumerate(reversed(grid.children)):
            if i == self.current_index:
                btn.background_color = (0.2, 0.5, 0.9, 1)
            elif i in self.user_answers:
                btn.background_color = (0.2, 0.7, 0.3, 1)
            else:
                btn.background_color = (0.7, 0.7, 0.7, 1)

    def jump_to_question(self, index):
        self.current_index = index
        self.display_current_question()

    def display_current_question(self):
        if not self.questions:
            return

        q = self.questions[self.current_index]
        q_id, cat, q_text, img_path, img_blob, opt_a, opt_b, opt_c, correct_answer, points, learning_status, difficulty = q

        self.ids.q_header_label.text = f"Otázka č. {self.current_index + 1} za {points} b"
        self.ids.q_category_label.text = cat
        self.ids.q_text_label.text = q_text

        self.ids.opt_a_btn.text = f"A)  {opt_a}"
        self.ids.opt_b_btn.text = f"B)  {opt_b}"
        self.ids.opt_c_btn.text = f"C)  {opt_c}"
        self.update_top_grid_colors()

        self.reset_option_colors()
        selected = self.user_answers.get(self.current_index)
        if selected == 0:
            self.ids.opt_a_btn.background_color = (0.2, 0.5, 0.9, 1)
        elif selected == 1:
            self.ids.opt_b_btn.background_color = (0.2, 0.5, 0.9, 1)
        elif selected == 2:
            self.ids.opt_c_btn.background_color = (0.2, 0.5, 0.9, 1)

        img_container = self.ids.test_image_container
        img_container.clear_widgets()
        if img_blob:
            img_w = blob_to_kivy_image(img_blob)
            if img_w:
                img_w.size_hint = (1, 1)
                img_container.add_widget(img_w)

    def set_orientation(self, mode):
        App.get_running_app().set_orientation(mode)

    def select_answer(self, option_index):
        self.user_answers[self.current_index] = option_index
        self.display_current_question()
        self.update_top_grid_colors()

    def reset_option_colors(self):
        default_color = (0.9, 0.9, 0.9, 1)
        self.ids.opt_a_btn.background_color = default_color
        self.ids.opt_b_btn.background_color = default_color
        self.ids.opt_c_btn.background_color = default_color

    def next_question(self):
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            self.display_current_question()

    def prev_question(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_question()

    def finish_test(self):
        if self.timer_event:
            self.timer_event.cancel()

        duration = int(time.time() - self.start_timestamp)
        total_points = 0
        earned_points = 0
        detailed_results = []
        category_results = {}

        for idx, q in enumerate(self.questions):
            q_id, cat, q_text, img_path, img_blob, opt_a, opt_b, opt_c, correct_answer, points, learning_status, difficulty = q
            total_points += points

            user_ans = self.user_answers.get(idx)
            is_correct = (user_ans == correct_answer)

            if is_correct:
                earned_points += points

            database.update_question_after_test(q_id, is_correct)

            if cat not in category_results:
                category_results[cat] = {"total": 0, "correct": 0, "earned_pts": 0, "total_pts": 0}
            category_results[cat]["total"] += 1
            category_results[cat]["total_pts"] += points
            if is_correct:
                category_results[cat]["correct"] += 1
                category_results[cat]["earned_pts"] += points

            detailed_results.append({
                "num": idx + 1,
                "question": q,
                "user_ans": user_ans,
                "correct_ans": correct_answer,
                "is_correct": is_correct
            })

        database.save_test_result(earned_points, total_points, duration, category_results)

        summary_screen = self.manager.get_screen("test_summary")
        summary_screen.load_summary(earned_points, total_points, duration, detailed_results, category_results)
        self.manager.current = "test_summary"


class TestSummaryScreen(Screen):
    detailed_results_data = []
    current_detail_index = 0

    def load_summary(self, earned, total, duration, results, category_results):
        self.detailed_results_data = results
        self.current_detail_index = 0

        percentage = (earned / total * 100) if total > 0 else 0
        minutes = duration // 60
        seconds = duration % 60

        self.ids.summary_score_label.text = f"Získali ste {earned} / {total} bodov (Úspešnosť: {percentage:.1f}%)"
        self.ids.summary_time_label.text = f"Čas vyplnenia: {minutes:02d}:{seconds:02d}"

        if percentage >= 90:
            self.ids.summary_status_label.text = "Výsledok testu: uspeli ste. 🟢"
        else:
            self.ids.summary_status_label.text = "Výsledok testu: neuspeli ste. 🔴"

        grid = self.ids.summary_grid
        grid.clear_widgets()

        for res in results:
            q_num = res["num"]
            is_correct = res["is_correct"]

            btn = Button(
                text=str(q_num),
                size_hint_x=None,
                width=35,
                background_color=(0.2, 0.7, 0.3, 1) if is_correct else (0.8, 0.2, 0.2, 1)
            )
            btn.bind(on_press=lambda instance, idx=q_num - 1: self.jump_to_detail(idx))
            grid.add_widget(btn)

        self.build_categories_table(category_results)
        self.display_detail_question()

    def build_categories_table(self, category_results):
        cat_layout = self.ids.categories_table_layout
        cat_layout.clear_widgets()

        for cat_name, data in category_results.items():
            c_q = data["correct"]
            t_q = data["total"]
            e_p = data["earned_pts"]
            t_p = data["total_pts"]
            pct = (e_p / t_p * 100) if t_p > 0 else 0

            row = BoxLayout(size_hint_y=None, height=35, spacing=10)

            lbl_name = Label(text=cat_name, size_hint_x=0.5, halign="left", text_size=(350, None), font_size=13)
            lbl_q = Label(text=f"{c_q}/{t_q}", size_hint_x=0.15, font_size=13)
            lbl_pts = Label(text=f"{e_p}/{t_p}", size_hint_x=0.15, font_size=13)
            lbl_pct = Label(text=f"{pct:.0f}%", size_hint_x=0.2, color=(0.1, 0.6, 0.2, 1) if pct >= 80 else (0.8, 0.2, 0.2, 1), bold=True, font_size=13)

            row.add_widget(lbl_name)
            row.add_widget(lbl_q)
            row.add_widget(lbl_pts)
            row.add_widget(lbl_pct)

            cat_layout.add_widget(row)

    def jump_to_detail(self, index):
        self.current_detail_index = index
        self.display_detail_question()

    def next_detail(self):
        if self.current_detail_index < len(self.detailed_results_data) - 1:
            self.current_detail_index += 1
            self.display_detail_question()

    def prev_detail(self):
        if self.current_detail_index > 0:
            self.current_detail_index -= 1
            self.display_detail_question()

    def display_detail_question(self):
        if not self.detailed_results_data:
            return

        res = self.detailed_results_data[self.current_detail_index]
        q_num = res["num"]
        q = res["question"]
        user_ans = res["user_ans"]
        correct_ans = res["correct_ans"]

        _, cat, q_text, img_path, img_blob, opt_a, opt_b, opt_c, correct_answer, points, _, _ = q

        self.ids.det_header.text = f"Otázka č. {q_num} [{cat}] za {points} b"
        self.ids.det_text.text = q_text

        self.ids.det_opt_a.text = f"A) {opt_a}"
        self.ids.det_opt_b.text = f"B) {opt_b}"
        self.ids.det_opt_c.text = f"C) {opt_c}"

        for idx, btn in enumerate([self.ids.det_opt_a, self.ids.det_opt_b, self.ids.det_opt_c]):
            btn.background_color = (0.9, 0.9, 0.9, 1)
            if idx == correct_ans:
                btn.background_color = (0.2, 0.7, 0.3, 1)
            if idx == user_ans and idx != correct_ans:
                btn.background_color = (0.8, 0.2, 0.2, 1)

        container = self.ids.det_image_container
        container.clear_widgets()
        if img_blob:
            img_w = blob_to_kivy_image(img_blob)
            if img_w:
                container.add_widget(img_w)


class WindowManager(ScreenManager):
    pass


class DrivingTestApp(App):
    orientation_mode = StringProperty("Automaticky")

    def build(self):
        database.init_db()
        Builder.load_file(kv_path)
        return WindowManager()

    def on_start(self):
        self.set_orientation(self.orientation_mode)

    def set_orientation(self, mode):
        orientation_values = {
            "Automaticky": 10,
            "Na výšku": 1,
            "Na šírku": 0,
        }
        if mode not in orientation_values:
            raise ValueError(f"Nepodporovaná orientácia: {mode}")

        self.orientation_mode = mode
        if platform == "android":
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            activity.setRequestedOrientation(orientation_values[mode])

if __name__ == "__main__":
    DrivingTestApp().run()
