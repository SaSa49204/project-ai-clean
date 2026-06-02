import numpy as np
import pandas as pd
import requests
import os
import PyPDF2

from langdetect import detect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI


class FAQBot:
    def __init__(self, excel_path: str, threshold: float = 0.5):

        self.excel_path = excel_path
        self.threshold = threshold  

        self.questions_en = []
        self.answers_en = []
        self.questions_ar = []
        self.answers_ar = []

        self.vectorizer_en = None
        self.matrix_en = None
        self.vectorizer_ar = None
        self.matrix_ar = None

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.history = {}

        self.backend_url = "https://graduationproject48.runasp.net/api"
        self.token = None

        self._load_data()
        self._build_models()

# ================= REQUEST =================
    def _safe_get(self, url):
        try:
            headers = {}

            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            r = requests.get(url, headers=headers)

            if r.status_code == 200:
                return r.json()

            return None

        except Exception as e:
            print("ERROR:", e)
            return None
# ============= Data ====================
    def _load_data(self):
        ext = os.path.splitext(self.excel_path)[1].lower()

        if ext == ".csv":
            df = pd.read_csv(self.excel_path)
        else:
            df = pd.read_excel(self.excel_path)

        self.questions_en = df["question"].dropna().tolist()
        self.answers_en = df["answer"].dropna().tolist()

        self.questions_ar = df["question_ar"].dropna().tolist()
        self.answers_ar = df["answer_ar"].dropna().tolist()

# ================= MODELS =================
    def _build_models(self):
        self.vectorizer_en = TfidfVectorizer()
        self.matrix_en = self.vectorizer_en.fit_transform(self.questions_en)

        self.vectorizer_ar = TfidfVectorizer()
        self.matrix_ar = self.vectorizer_ar.fit_transform(self.questions_ar)

# ================= LANG =================
    def _detect_lang(self, text):

        for ch in text:

            if '\u0600' <= ch <= '\u06FF':
                return "ar"

        return "en"

# ================= BACKEND =================
    def _get_gpa(self):
        data = self._safe_get(f"{self.backend_url}/Student/gpa")

        print("DEBUG GPA DATA:", data)

        if not data:
            return None

        # لو dict
        if isinstance(data, dict):
            # 👇 يدعم الشكلين
            if "cumulativeGpa" in data:
                return data.get("cumulativeGpa")

            return data.get("data", {}).get("gpa")

        # لو list
        if isinstance(data, list):
            if len(data) > 0:
                first = data[0]
                if isinstance(first, dict):

                    # 👇 يدعم cumulativeGpa
                    if "cumulativeGpa" in first:
                        return first.get("cumulativeGpa")

                    return first.get("gpa")

        return None

    def _get_current_courses(self):
        data = self._safe_get(f"{self.backend_url}/Enrollment/current-courses")

        print("DEBUG CURRENT:", data)

        if isinstance(data, dict):
            if isinstance(data.get("data"), list) and data["data"]:
                return data["data"]

        if isinstance(data, list):
            return data

        return [
            {"courseName": "Data Structures"},
            {"courseName": "Discrete Mathematics"}
        ]

    def _get_previous_courses(self):
        data = self._safe_get(f"{self.backend_url}/Enrollment/previous-courses")

        print("DEBUG PREVIOUS:", data)

        if isinstance(data, dict):
            if isinstance(data.get("data"), list) and data["data"]:
                return data["data"]

        if isinstance(data, list):
            return data

        return [
            {"courseName": "Intro to Computer Science"},
            {"courseName": "Computer Programming"}
        ]
    def _format_gpa(self, gpa, lang="en"):

        if gpa is None:
            return "No GPA" if lang == "en" else "لا يوجد معدل"

        if lang == "ar":
            if gpa < 2:
                return f"معدلك {gpa} ⚠️ حاول تقلل المواد وتركز"
            elif gpa < 3:
                return f"معدلك {gpa} 👍 كويس"
            else:
                return f"معدلك {gpa} 🔥 ممتاز"
        else:
            if gpa < 2:
                return f"Your GPA is {gpa} ⚠️ Try to reduce load"
            elif gpa < 3:
                return f"Your GPA is {gpa} 👍 Good"
            else:
                return f"Your GPA is {gpa} 🔥 Excellent"

# ================= SMART AI TITLE =================
    def generate_title(self, question):

        intent = self._detect_intent(question)

        # 👇 titles 
        if intent == "gpa":
            return "GPA Check"

        elif intent == "current":
            return "Current Courses"

        elif intent == "previous":
            return "Completed Courses"

        elif intent == "study_plan":
            return "Study Plan"

        elif intent == "recommend":
            return "Course Recommendations"

        elif intent == "roadmap":
            return "Graduation Roadmap"

        # 👇 fallback للـ AI
        try:
            res = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """
Generate a short smart chat title (max 4 words).

Rules:
- Based on user question
- Same language
- No symbols
- Clear and meaningful
"""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                temperature=0.3
            )

            title = res.choices[0].message.content.strip()

            return " ".join(title.split()[:4])

        except Exception as e:
            print("TITLE ERROR:", e)
            return question[:25]
# ================= HELPERS =================
    def _extract_names(self, courses):
        names = []

        for c in courses:
            if isinstance(c, dict):
                name = (
                    c.get("courseName")
                    or c.get("name")
                    or c.get("title")
                    or ""
                )
            else:
                name = str(c)

            # 🔥 normalize
            name = name.strip()

            names.append(name)

        return names

# ================= STUDENT YEAR =================
    def _detect_student_year(self, completed):

        count = len(completed)

        if count < 6:
            return "First Year"

        elif count < 12:
            return "Second Year"

        elif count < 18:
            return "Third Year"

        return "Fourth Year"
# ================= COURSE GRAPH =================
    COURSE_GRAPH = [
    # 🔹 First Year
    {"name": "Intro to Computer Science", "prereq": []},
    {"name": "Computer Programming", "prereq": ["Intro to Computer Science"]},
    {"name": "Discrete Mathematics", "prereq": []},
    {"name": "Linear Algebra", "prereq": []},
    {"name": "Electronics", "prereq": []},
    {"name": "Physics", "prereq": []},

    # 🔹 Second Year
    {"name": "Data Structures", "prereq": ["Computer Programming"]},
    {"name": "Logic Design", "prereq": ["Electronics"]},
    {"name": "Object Oriented Programming", "prereq": ["Computer Programming"]},
    {"name": "File Processing", "prereq": ["Computer Programming"]},
    {"name": "Assembly Language", "prereq": ["Logic Design"]},
    {"name": "Statistics and Probability", "prereq": ["Discrete Mathematics"]},

    # 🔹 Third Year
    {"name": "Algorithms", "prereq": ["Data Structures"]},
    {"name": "Databases", "prereq": ["Data Structures"]},
    {"name": "Operating Systems", "prereq": ["Data Structures"]},
    {"name": "Computer Graphics", "prereq": ["Data Structures"]},
    {"name": "Software Engineering", "prereq": ["Data Structures"]},
    {"name": "Artificial Intelligence", "prereq": ["Algorithms"]},
    {"name": "Neural Networks", "prereq": ["Artificial Intelligence"]},

    # 🔹 Fourth Year
    {"name": "Machine Learning", "prereq": ["Artificial Intelligence"]},
    {"name": "Cloud Computing", "prereq": ["Operating Systems"]},
    {"name": "Computer Security", "prereq": ["Operating Systems"]},
    {"name": "Distributed Systems", "prereq": ["Operating Systems"]},
    {"name": "Parallel Processing", "prereq": ["Operating Systems"]},
    {"name": "Data Warehousing", "prereq": ["Databases"]},
    {"name": "Internet of Things", "prereq": ["Computer Networks"]},

    # 🔹 Supporting Courses
    {"name": "Computer Networks", "prereq": ["Data Structures"]},
    {"name": "Web Programming", "prereq": ["Data Structures"]},
    {"name": "Systems Analysis and Design", "prereq": ["Data Structures"]},

    # 🔹 Graduation
    {"name": "Senior Project 1", "prereq": []},
    {"name": "Graduation Project 2", "prereq": ["Senior Project 1"]},
]
    # ================= ALL COURSES =================
    def _all_courses(self):

        grouped = {
            "First Year": [],
            "Second Year": [],
            "Third Year": [],
            "Fourth Year": []
        }

        for c in self.COURSE_GRAPH:

            name = c["name"]

            if name in [
                "Intro to Computer Science",
                "Computer Programming",
                "Discrete Mathematics",
                "Linear Algebra",
                "Electronics",
                "Physics"
            ]:
                grouped["First Year"].append(name)

            elif name in [
                "Data Structures",
                "Logic Design",
                "Object Oriented Programming",
                "File Processing",
                "Assembly Language",
                "Statistics and Probability"
            ]:
                grouped["Second Year"].append(name)

            elif name in [
                "Algorithms",
                "Databases",
                "Operating Systems",
                "Computer Graphics",
                "Software Engineering",
                "Artificial Intelligence",
                "Neural Networks"
            ]:
                grouped["Third Year"].append(name)

            else:
                grouped["Fourth Year"].append(name)

        return grouped
    


    # ================= COURSE DIFFICULTY =================
    COURSE_DIFFICULTY = {
    "Intro to Computer Science": "easy",
    "Computer Programming": "medium",
    "Discrete Mathematics": "medium",
    "Linear Algebra": "medium",
    "Electronics": "medium",
    "Physics": "medium",

    "Data Structures": "hard",
    "Logic Design": "medium",
    "Object Oriented Programming": "medium",
    "File Processing": "easy",
    "Assembly Language": "hard",
    "Statistics and Probability": "medium",

    "Algorithms": "hard",
    "Databases": "medium",
    "Operating Systems": "hard",
    "Computer Graphics": "medium",
    "Software Engineering": "medium",
    "Artificial Intelligence": "hard",
    "Neural Networks": "hard",

    "Machine Learning": "hard",
    "Cloud Computing": "medium",
    "Computer Security": "medium",
    "Distributed Systems": "hard",
    "Parallel Processing": "hard",
    "Data Warehousing": "medium",
    "Internet of Things": "medium",

    "Computer Networks": "medium",
    "Web Programming": "easy",
    "Systems Analysis and Design": "medium",

    "Senior Project 1": "medium",
    "Graduation Project 2": "hard",
}
# ================= SMART RECOMMEND =================
    def _recommend_smart(self):

        completed = self._extract_names(
            self._get_previous_courses()
        )

        current = self._extract_names(
            self._get_current_courses()
    )

        gpa = self._get_gpa()

        available = []

        for course in self.COURSE_GRAPH:

            name = course["name"]

            if name in completed:
                continue

            if name in current:
                continue

            if all(p in completed for p in course["prereq"]):
                available.append(name)

        available = self._filter_by_gpa(available, gpa)

        year = self._detect_student_year(completed)

        if gpa and gpa < 2:
            return available[:2]

        elif gpa and gpa < 3:
            return available[:4]

        return available[:6]
    
# ================= EXPLAIN COURSE =================
    def _explain_course(self, course_name, lang="en"):

        prompt = f"""
اشرح مادة {course_name} كأنك أستاذ جامعي وخبير أكاديمي.

يجب أن يكون الرد منظمًا بهذا الشكل:

📘 اسم المادة

🎯 ما هي المادة؟
شرح مبسط وواضح.

📚 أهم الموضوعات:
- ...
- ...
- ...

💻 التطبيقات العملية:
- ...
- ...
- ...

⚠️ مستوى الصعوبة:
سهل / متوسط / صعب مع التوضيح.

🗺️ Roadmap للمذاكرة:
الأسبوع الأول:
...

الأسبوع الثاني:
...

📖 أفضل المصادر:
YouTube:
- اسم القناة

Courses:
- اسم الكورس

Books:
- اسم الكتاب

💡 نصائح للتفوق:
- ...
- ...

اكتب باللغة {"العربية" if lang=="ar" else "الإنجليزية"} فقط.
"""

        return self._ask_ai(
            prompt,
            lang=lang
        )
    
# ================= SMART PLAN =================
    def _smart_plan(self, lang="en", student_id=None):

        gpa = self._get_gpa()

        current = self._extract_names(
            self._get_current_courses()
        )

        completed = self._extract_names(
            self._get_previous_courses()
        )

        if lang == "ar":

            prompt = f"""
الطالب معدله {gpa}

المواد الحالية:
{current}

المواد اللي خلصها:
{completed}

اعمل خطة مذاكرة ذكية ومناسبة لمستواه.
"""

        else:

            prompt = f"""
Student GPA: {gpa}

Current courses:
{current}

Completed courses:
{completed}

Create smart study plan.
"""

        return self._ask_ai(
            prompt,
            student_id,
            lang
        )
    
# ================= AVAILABLE COURSES =================
    def _get_available_courses(self, completed):
        available = []

        for course in self.COURSE_GRAPH:
            if course["name"] in completed:
                continue

            if all(p in completed for p in course["prereq"]):
                available.append(course["name"])

        return available
    
# ================= FILTER BY GPA =================
    def _filter_by_gpa(self, courses, gpa):

        if not gpa:
            return courses

        if gpa >= 3.2:
            return courses  # 🔥 كله متاح

        elif gpa >= 2.5:
            return [c for c in courses if self.COURSE_DIFFICULTY.get(c) != "hard"]

        else:
            easy_courses = [c for c in courses if self.COURSE_DIFFICULTY.get(c) == "easy"]

            return easy_courses if easy_courses else courses[:2]

# ================= ROADMAP =================
    def _generate_roadmap(self):
        completed = self._extract_names(self._get_previous_courses())
        gpa = self._get_gpa()

        roadmap = []
        temp_done = completed.copy()

        for _ in range(4):
            term = []
            year = self._detect_student_year(temp_done)

            for course in self.COURSE_GRAPH:
                name = course["name"]

                if name in temp_done:
                    continue

                if "project" in name.lower() and year != "Fourth Year":
                    continue

                if all(p in temp_done for p in course["prereq"]):
                    term.append(name)

            if not term:
                break

            term = term[:5]
            roadmap.append(term)

            temp_done.extend(term)

        return roadmap

# ================= AI =================
    def _ask_ai(self, prompt, student_id=None, lang="en"):

        memory = self._get_memory(student_id)

        gpa = self._get_gpa()

        completed = self._extract_names(
            self._get_previous_courses()
        )

        current = self._extract_names(
            self._get_current_courses()
        )

        year = self._detect_student_year(completed)

        res = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a professional academic advisor like ChatGPT.

Rules:

Always return answers in Markdown.

Use headings.

Format exactly like:

# Title

## Overview

text

## Important Points

- Point 1
- Point 2
- Point 3

## Examples

- Example 1
- Example 2

## Resources

- Resource 1
- Resource 2

## Tips

- Tip 1
- Tip 2

Do NOT write everything in one paragraph.

Put each section on separate lines.

Respond only in the user's language.

Student Information:
- GPA: {gpa}
- Academic Year: {year}
- Completed Courses: {completed}
- Current Courses: {current}

Conversation History:
{memory}
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3
        )

        response = res.choices[0].message.content.strip()
        answer = answer.replace("## ", "\n\n## ")
        answer = answer.replace("# ", "\n\n# ")
        answer = answer.replace("- ", "\n• ")

        if "?" not in response:

            if lang == "ar":
                response += "\n\nتحب أساعدك أكتر؟"

            else:
                response += "\n\nDo you want more help?"

        return response

# ================= INTENT =================
    def _detect_intent(self, question):

        q = question.lower()

        if "gpa" in q or "معدل" in q:
            return "gpa"

        if "smart plan" in q or "خطة ذكية" in q:
            return "smart_plan"

        if "اشرح" in q or "شرح" in q or "explain" in q or "عرفني" in q:
            return "explain"

        if "تايه" in q or "مش فاهم" in q or "lost" in q:
            return "confused"

        if "roadmap" in q or "خطة تخرج" in q:
            return "roadmap"
        
        if "كم عدد المواد" in q:
            return "count_courses"

        if (
            "suggest" in q
            or "اخد ايه" in q
            or "study next" in q
            or "recommend" in q
            or "رشح" in q
        ):
            return "recommend"
        if (
            "خطة يوم" in q
            or "daily plan" in q
        ):
            return "daily_plan"

        if (
            "خطة اسبوع" in q
            or "weekly plan" in q
        ):
            return "weekly_plan"

        if (
            "خطة شهر" in q
            or "monthly plan" in q
            or "شهر" in q
        ):
            return "monthly_plan"
        
        if (
            "all courses" in q
            or "مواد الاربع سنين" in q
            or "كل المواد" in q
            or "مواد الكلية" in q
        ):
            return "all_courses"
        
        if (
            "مصادر" in q
            or "كورسات" in q
            or "resources" in q
            or "best resources" in q
       ):
            return "resources"
        
        if (
            "لخص الملف" in q
            or "summarize file" in q
        ):
            return "summarize_pdf"

        if (
            "اعمل امتحان" in q
            or "اختبرني" in q
            or "quiz" in q
        ):
            return "quiz"

        return "faq"

# ================= FAQ =================
    def _faq(self, q, lang):
        vec = self.vectorizer_ar if lang == "ar" else self.vectorizer_en
        mat = self.matrix_ar if lang == "ar" else self.matrix_en
        answers = self.answers_ar if lang == "ar" else self.answers_en
        
        if mat.shape[0] == 0:
            return None, 0
        
        q = q.strip().lower()
        sims = cosine_similarity(vec.transform([q]), mat)[0]
        idx = np.argmax(sims)
        return answers[idx], sims[idx]

# ================= HISTORY =================
    def _save_history(self, sid, q, a):

        if not sid:
            return

        self.history.setdefault(sid, [])

        self.history[sid].append({
            "q": q,
            "a": a
        })

        self.history[sid] = self.history[sid][-20:]


#============== PDF READING =================
    def _read_pdf(self, path):

        text = ""

        with open(path, "rb") as file:

            reader = PyPDF2.PdfReader(file)

            for page in reader.pages:

                content = page.extract_text()

                if content:
                    text += content

        return text

#================ LATEST PDF =================
    def _get_latest_pdf(self):

        with open(
            "uploads/latest.txt",
            "r",
            encoding="utf-8"
        ) as f:

            return f.read().strip()

# ================= MEMORY =================
    def _get_memory(self, sid):
 
        history = self.history.get(sid, [])[-20:]

        memory = ""

        for h in history:
            memory += f"User: {h['q']}\nBot: {h['a']}\n"

        return memory
    
#=================== CLEAN RESPONSE =================
    def _clean_response(self, text):

        text = text.replace("###", "\n\n")
        text = text.replace("##", "\n\n")
        text = text.replace("**", "")

        for i in range(1, 30):
            text = text.replace(
                f"{i}.",
                f"\n\n{i}."
            )

        text = text.replace("•", "\n•")

        text = text.replace("📘", "\n\n📘")
        text = text.replace("🎯", "\n\n🎯")
        text = text.replace("📚", "\n\n📚")
        text = text.replace("💻", "\n\n💻")
        text = text.replace("⚠️", "\n\n⚠️")
        text = text.replace("🗺️", "\n\n🗺️")
        text = text.replace("📖", "\n\n📖")
        text = text.replace("💡", "\n\n💡")

        return text.strip()

# ================= MAIN =================
    def answer(self, question, student_id=None):
 
        lang = self._detect_lang(question)

        original_question = question

        # ================= FAQ FIRST =================
        intent = self._detect_intent(question)

        faq_answer, score = self._faq(question, lang)

        # FAQ فقط لو intent faq
        if intent == "faq" and faq_answer and score > 0.7:

            self._save_history(
                student_id,
                question,
                faq_answer
            )

            return {
                "answer": faq_answer
            }

        # ================= MEMORY =================
        memory = self._get_memory(student_id)

        if memory:

            question = f"""
                Conversation:
                {memory}

                Current Question:
                {question}
            """

        # ================= INTENT =================

        # ===== GPA =====
        if intent == "gpa":

            gpa = self._get_gpa()

            answer = self._format_gpa(
                gpa,
                lang
            )

        # ===== CURRENT =====
        elif intent == "current":

            names = self._extract_names(
                self._get_current_courses()
            )

            answer = (
                "\n".join(names)
                if names
                else "No courses"
            )

        # ===== PREVIOUS =====
        elif intent == "previous":

            names = self._extract_names(
                self._get_previous_courses()
            )

            answer = (
                "\n".join(names)
                if names
                else "No previous"
            )
        #===== COUNT COURSES =====
        elif intent == "count_courses":

            count = len(self.COURSE_GRAPH)

            if lang == "ar":
                answer = f"📚 إجمالي عدد المواد في الخطة الدراسية: {count}"
            else:
                answer = f"📚 Total courses in study plan: {count}"
        # ===== STUDY PLAN =====
        elif intent == "study_plan":

            gpa = self._get_gpa()

            current = self._extract_names(
                self._get_current_courses()
            )

            prompt = f"""
Student GPA: {gpa}
Current courses: {current}

Give smart study plan.
"""

            answer = self._ask_ai(
                prompt,
                student_id,
                lang
            )

        # ===== RECOMMEND =====
        elif intent == "recommend":

            courses = self._recommend_smart()

            if not courses:

                answer = (
                    "يبدو أنك أنهيت معظم المواد 🎉"
                    if lang == "ar"
                    else "You seem to have completed most courses 🎉"
                )

            else:

                if lang == "ar":

                    answer = "📚 المواد المقترحة:\n"

                else:

                    answer = "📚 Recommended Courses:\n"

                for c in courses:
                    answer += f"• {c}\n"

        # ===== ROADMAP =====
        elif intent == "roadmap":

            plan = self._generate_roadmap()

            if lang == "ar":

                answer = "🧭 الخطة الدراسية:\n\n"

                for i, term in enumerate(plan, 1):

                    answer += f"\n📚 ترم {i}\n\n"
                    for course in term:
                        answer += f"• {course}\n"

            else:

                answer = "🧭 Study Roadmap:\n\n"

                for i, term in enumerate(plan, 1):

                    answer += f"\n📚 Term {i}\n\n"
                    for course in term:
                        answer += f"• {course}\n"

        # ===== EXPLAIN =====
        elif intent == "explain":

            course_name = (
                original_question
                .replace("اشرح", "")
                .replace("شرح", "")
                .replace("explain", "")
                .strip()
            )

            answer = self._explain_course(
                course_name,
                lang
            )

        # ===== SMART PLAN =====
        elif intent == "smart_plan":

            answer = self._smart_plan(
                lang,
                student_id
            )

        # ===== CONFUSED =====
        elif intent == "confused":

            if lang == "ar":

                prompt = (
                    "الطالب تايه ومحتاج تنظيم مذاكرة ودعم"
                )

            else:

                prompt = (
                    "Student feels lost and needs guidance"
                )

            answer = self._ask_ai(
                prompt,
                student_id,
                lang
            )

        # ===== ALL COURSES =====
        elif intent == "all_courses":

            data = self._all_courses()

            if lang == "ar":

                answer = "📚 مواد الأربع سنين:\n\n"

                mapping = {
                    "First Year": "الفرقة الأولى",
                    "Second Year": "الفرقة الثانية",
                    "Third Year": "الفرقة الثالثة",
                    "Fourth Year": "الفرقة الرابعة"
                }

                for year, courses in data.items():

                    answer += f"{mapping[year]}:\n"

                    for c in courses:
                        answer += f"• {c}\n"

                    answer += "\n"

            else:

                answer = "📚 All CS Courses:\n\n"

                for year, courses in data.items():

                    answer += f"{year}:\n"

                    for c in courses:
                        answer += f"• {c}\n"

                    answer += "\n"

        # ===== DAILY PLAN =====
        elif intent == "daily_plan":

            prompt = f"""
Create a one day study plan.

Language:
{"Arabic" if lang == "ar" else "English"}

Student GPA:
{self._get_gpa()}

Current Courses:
{self._extract_names(self._get_current_courses())}

Rules:
- Hour by hour
- Simple
- Organized
- No markdown
"""

            answer = self._ask_ai(
                prompt,
                student_id,
                lang
            )

        # ===== WEEKLY PLAN =====
        elif intent == "weekly_plan":

            prompt = f"""
Create a one week study plan.

Language:
{"Arabic" if lang == "ar" else "English"}

Student GPA:
{self._get_gpa()}

Current Courses:
{self._extract_names(self._get_current_courses())}

Rules:
- Day by day
- Balanced schedule
- Clear tasks
- No markdown
"""

            answer = self._ask_ai(
                prompt,
                student_id,
                lang
            )

        # ===== MONTHLY PLAN =====
        elif intent == "monthly_plan":

            prompt = f"""
Create a one month study plan.

Language:
{"Arabic" if lang == "ar" else "English"}

Student GPA:
{self._get_gpa()}

Current Courses:
{self._extract_names(self._get_current_courses())}

Rules:
- Weekly goals
- Study targets
- Revision days
- Realistic schedule
- No markdown
"""

            answer = self._ask_ai(
                prompt,
                student_id,
                lang
            )            
        # ===== RESOURCES =====
        elif intent == "resources":

            answer = self._ask_ai(
        """
Give learning resources.

Required:

📺 YouTube
- Name
- URL

🎓 Courses
- Name
- URL

📚 Books

🌐 Websites

Provide REAL URLs.

Organize response clearly.

Respond in same language.
""",
            student_id,
            lang
    )
        # ===== PDF SUMMARY =====
        elif intent == "summarize_pdf":

            pdf_text = self._read_pdf(
                self._get_latest_pdf()
            )
            answer = self._ask_ai(
                f"""
Summarize this PDF document:

{pdf_text[:12000]}
""",
            student_id,
            lang
        )


        # ===== PDF QUIZ =====
        elif intent == "quiz":

            pdf_text = self._read_pdf(
                self._get_latest_pdf()
            )

            answer = self._ask_ai(
                f"""
Create an exam from this content:

{pdf_text[:12000]}

Generate:

5 MCQ Questions
3 True/False
2 Essay Questions

Use the same language.
""",
            student_id,
            lang
        )
        

        # ===== AI =====
        else:

            answer = self._ask_ai(
                question,
                student_id,
                lang
            )

        # ================= SAVE =================
        self._save_history(
            student_id,
            original_question,
            answer
        )

        answer = self._clean_response(answer)
        return {
            "answer": answer
        }