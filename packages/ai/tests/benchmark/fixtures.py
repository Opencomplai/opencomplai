"""Labelled synthetic programs for the Annex III code-signal benchmark.

Each fixture is a small program (2 to 4 files) with an expected Annex III area
(1 to 8) or ``None`` when no Annex III area applies. The labels were written from
the Annex III text as encoded in ``opencomplai_core.knowledge.annex_iii`` before
any measurement was taken, and are never edited to make the matcher agree: a
miss stays a false negative and a spurious hit stays a false positive.

The fixture text lives in ``_RAW`` in a small line format::

    @@ <name>
    area: <1..8 | none>
    purpose: <declared purpose>
    why: <Annex III point, or the reason no area applies>
    ## <relative path>
    <file text>

``_parse`` adds nothing to the files: each program's text is exactly what is
written under its ``##`` lines, so the matcher sees only that code, never the
declared purpose (the purpose is passed to the scan separately).

Some labelled programs open a file with a one-line comment such as a project
writes about its own module. That is the only way a multi-word Annex III phrase
reaches the matcher from code, so those comments keep the phrase half of the
matcher measured; no look-alike carries one.
"""

from __future__ import annotations

BENCHMARK_META = {
    "source": (
        "Annex III as encoded in opencomplai_core.knowledge.annex_iii "
        "(area names and sub-points); synthetic programs written for this benchmark"
    ),
    "confidence": "medium",
    "needs_founder_review": True,
    "labelled_by": "benchmark author, single labeller, no second review",
    "date": "2026-10-12",
}

_RAW = r"""
@@ crowd-face-search
area: 1
purpose: Identify people in live CCTV footage of a train station by matching faces against a watchlist database
why: Annex III biometrics 1(a), remote biometric identification of persons at a distance against a reference database
## requirements.txt
face_recognition
opencv-python
numpy
## app.py
import cv2
import face_recognition
import numpy as np

from watchlist import load_watchlist

names, encodings = load_watchlist("watchlist.db")

def match_frame(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    found = []
    for enc in face_recognition.face_encodings(rgb, boxes):
        dist = face_recognition.face_distance(encodings, enc)
        best = int(np.argmin(dist))
        if dist[best] < 0.5:
            found.append(names[best])
    return found

def run(stream_url):
    cap = cv2.VideoCapture(stream_url)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for person in match_frame(frame):
            print("watchlist hit:", person)
## watchlist.py
import pickle
import sqlite3


def load_watchlist(path):
    con = sqlite3.connect(path)
    rows = con.execute("select name, encoding from watchlist").fetchall()
    names = [r[0] for r in rows]
    encodings = [pickle.loads(r[1]) for r in rows]
    return names, encodings

@@ shopper-face-identification
area: 1
purpose: Recognise returning shoppers at store entrances by comparing camera faces with enrolled loyalty-member face templates
why: Annex III biometrics 1(a), identification of natural persons at a distance without their active involvement
## requirements.txt
deepface
opencv-python
pandas
## entrance.py
import cv2
from deepface import DeepFace

from notify import notify_staff

GALLERY_DIR = "members_gallery"

def identify_visitor(frame):
    hits = DeepFace.find(
        img_path=frame,
        db_path=GALLERY_DIR,
        model_name="ArcFace",
        enforce_detection=False,
    )
    if hits and len(hits[0]) > 0:
        return hits[0].iloc[0]["identity"]
    return None

def watch_entrance(camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        member = identify_visitor(frame)
        if member:
            notify_staff(member)
## notify.py
def notify_staff(member):
    print("member arrived:", member)

@@ face-attribute-categorizer
area: 1
purpose: Estimate the gender and age band of people in front of a digital signage screen from camera images to count audience demographics
why: Annex III biometrics 1(b), biometric categorisation inferring protected attributes from facial images
## requirements.txt
torch
torchvision
opencv-python
## net.py
# Biometric categorization net: age band and gender from a face crop.
import torch
from torchvision import models

AGE_BANDS = ["0-17", "18-34", "35-54", "55+"]


class FaceAttributeNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = models.resnet18(weights=None)
        self.backbone.fc = torch.nn.Linear(512, len(AGE_BANDS) + 2)

    def forward(self, x):
        return self.backbone(x)
## audience.py
import torch

from net import AGE_BANDS, FaceAttributeNet

net = FaceAttributeNet()
net.load_state_dict(torch.load("attributes.pt"))
net.eval()


def estimate_demographics(face_batch):
    with torch.no_grad():
        out = net(face_batch)
    gender = out[:, :2].argmax(dim=1)
    age = out[:, 2:].argmax(dim=1)
    return [
        ("female" if g == 0 else "male", AGE_BANDS[a]) for g, a in zip(gender, age)
    ]

@@ kiosk-emotion-reader
area: 1
purpose: Detect the emotion of customers at a service kiosk from their facial expressions to adapt the screen
why: Annex III biometrics 1(c), emotion recognition system working on facial expressions
## requirements.txt
fer
opencv-python
## kiosk.py
import cv2
from fer import FER

detector = FER(mtcnn=True)


def read_mood(frame):
    emotion, score = detector.top_emotion(frame)
    return emotion, score


def loop():
    cam = cv2.VideoCapture(0)
    while True:
        ok, frame = cam.read()
        if not ok:
            break
        emotion, score = read_mood(frame)
        if emotion in ("angry", "sad") and score and score > 0.6:
            show_calm_screen()


def show_calm_screen():
    print("switching to simplified layout")

@@ grid-load-balancer
area: 2
purpose: Dispatch set-points for transformers and feeders on a regional electricity distribution grid using a learned controller
why: Annex III critical infrastructure 2, safety component in the management and operation of the supply of electricity
## requirements.txt
torch
pandapower
numpy
## controller.py
import pandapower as pp
import torch


class FeederPolicy(torch.nn.Module):
    def __init__(self, n_buses, n_taps):
        super().__init__()
        self.body = torch.nn.Sequential(
            torch.nn.Linear(n_buses, 64),
            torch.nn.ReLU(),
            torch.nn.Linear(64, n_taps),
        )

    def forward(self, x):
        return self.body(x)


def dispatch_setpoints(net, policy):
    state = torch.tensor(net.res_bus.vm_pu.values, dtype=torch.float32)
    action = policy(state)
    for idx, tap in enumerate(action.round().int().tolist()):
        net.trafo.at[idx, "tap_pos"] = tap
    pp.runpp(net)
    return net
## scada_link.py
def push_setpoints(net, client):
    for idx, row in net.trafo.iterrows():
        client.write_register(1000 + idx, int(row["tap_pos"]))

@@ water-treatment-dosing
area: 2
purpose: Control chemical dosing pumps in a municipal drinking water treatment plant from sensor readings
why: Annex III critical infrastructure 2, safety component in the management and operation of water supply
## requirements.txt
scikit-learn
pandas
pymodbus
## dosing.py
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

FEATURES = ["turbidity", "flow_rate", "ph", "water_temp"]

history = pd.read_csv("plant_history.csv")
model = GradientBoostingRegressor().fit(history[FEATURES], history["chlorine_dose"])


def next_dose(reading):
    row = pd.DataFrame([reading])[FEATURES]
    return float(model.predict(row)[0])
## pump.py
from dosing import next_dose


def update_pump(client, reading):
    dose = next_dose(reading)
    client.write_register(40001, int(dose * 100))
    return dose

@@ traffic-signal-optimizer
area: 2
purpose: Adjust traffic light phase timings at city intersections to reduce congestion
why: Annex III critical infrastructure 2, safety component in the management and operation of road traffic
## requirements.txt
torch
numpy
## agent.py
# Road traffic management: picks the next signal phase for a junction.
import torch

PHASES = 4


class SignalAgent(torch.nn.Module):
    def __init__(self, n_lanes):
        super().__init__()
        self.q = torch.nn.Sequential(
            torch.nn.Linear(n_lanes, 32),
            torch.nn.ReLU(),
            torch.nn.Linear(32, PHASES),
        )

    def forward(self, queue_lengths):
        return self.q(queue_lengths)


def choose_phase(agent, queue_lengths):
    with torch.no_grad():
        return int(agent(torch.tensor(queue_lengths, dtype=torch.float32)).argmax())
## junction.py
from agent import SignalAgent, choose_phase

agent = SignalAgent(n_lanes=8)


def tick(sensors, controller):
    phase = choose_phase(agent, sensors.queue_lengths())
    controller.set_phase(phase, green_seconds=25)

@@ admissions-ranker
area: 3
purpose: Rank applicants to the university's master programmes and propose who is admitted
why: Annex III education 3(a), determining access or admission of persons to educational institutions
## requirements.txt
scikit-learn
pandas
## ranker.py
# Student selection algorithm used by the admissions office.
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

COLUMNS = ["gpa", "entrance_exam", "letters_score", "relevant_projects"]

past = pd.read_csv("past_admissions.csv")
model = RandomForestClassifier(n_estimators=200, random_state=0)
model.fit(past[COLUMNS], past["admitted"])


def rank_applicants(applicants: pd.DataFrame) -> pd.DataFrame:
    scored = applicants.copy()
    scored["p_admit"] = model.predict_proba(applicants[COLUMNS])[:, 1]
    return scored.sort_values("p_admit", ascending=False)
## report.py
from ranker import rank_applicants


def top_n(applicants, seats):
    return rank_applicants(applicants).head(seats)

@@ essay-grader
area: 3
purpose: Grade student essays automatically; the grade is entered in the course record
why: Annex III education 3(b), evaluating learning outcomes where the result steers the learning process
## requirements.txt
scikit-learn
pandas
## grader.py
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

labelled = pd.read_csv("marked_essays.csv")
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
reg = Ridge(alpha=1.0).fit(vec.fit_transform(labelled["text"]), labelled["mark"])


def mark_essay(text: str) -> float:
    raw = reg.predict(vec.transform([text]))[0]
    return round(min(max(raw, 0.0), 100.0), 1)
## gradebook.py
from grader import mark_essay


def record_marks(submissions, gradebook):
    for sub in submissions:
        gradebook[sub["student_id"]] = mark_essay(sub["text"])

@@ exam-proctor
area: 3
purpose: Monitor students through their webcams during online exams and flag suspected cheating
why: Annex III education 3(d), monitoring and detecting prohibited behaviour of students during tests
## requirements.txt
opencv-python
mediapipe
## monitor.py
# Online proctoring: flags frames where a candidate may be cheating.
import cv2
import mediapipe as mp

face_mesh = mp.solutions.face_mesh.FaceMesh(max_num_faces=2)


def check_frame(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb)
    faces = result.multi_face_landmarks or []
    flags = []
    if len(faces) == 0:
        flags.append("face_missing")
    if len(faces) > 1:
        flags.append("second_person")
    for face in faces:
        nose = face.landmark[1]
        if nose.x < 0.3 or nose.x > 0.7:
            flags.append("looking_away")
    return flags
## session.py
from monitor import check_frame


def run_exam(camera, report):
    while camera.is_open():
        frame = camera.read()
        for flag in check_frame(frame):
            report.add(flag)

@@ course-placement
area: 3
purpose: Assign new students to a course level from their placement questionnaire answers
why: Annex III education 3(c), assessing the appropriate level of education an individual will receive
## requirements.txt
scikit-learn
numpy
## placement.py
import numpy as np
from sklearn.tree import DecisionTreeClassifier

LEVELS = ["beginner", "intermediate", "advanced"]

answers = np.load("questionnaire_answers.npy")
levels = np.load("assigned_levels.npy")
tree = DecisionTreeClassifier(max_depth=5).fit(answers, levels)


def assign_level(student_answers):
    idx = int(tree.predict([student_answers])[0])
    return LEVELS[idx]
## enrol.py
from placement import assign_level


def enrol(student, form):
    student["course_level"] = assign_level(form["answers"])
    return student

@@ resume-screener
area: 4
purpose: Screen incoming CVs and rank job candidates for the recruiting team
why: Annex III employment 4(a), recruitment and selection including screening and evaluating candidates
## requirements.txt
scikit-learn
pandas
## screener.py
# Candidate ranking for the recruiting team: CVs against a job description.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def rank_resumes(job_text, resumes):
    vec = TfidfVectorizer(stop_words="english")
    matrix = vec.fit_transform([job_text, *[r["text"] for r in resumes]])
    sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    order = sims.argsort()[::-1]
    return [(resumes[i]["candidate"], float(sims[i])) for i in order]
## shortlist.py
from screener import rank_resumes


def shortlist(job, resumes, size=10):
    return rank_resumes(job["description"], resumes)[:size]

@@ interview-scorer
area: 4
purpose: Score recorded video interview answers of job applicants and recommend who proceeds to the next round
why: Annex III employment 4(a), evaluation of candidates in recruitment and selection
## requirements.txt
faster-whisper
scikit-learn
## transcribe.py
from faster_whisper import WhisperModel

model = WhisperModel("small")


def transcribe(path):
    segments, _ = model.transcribe(path)
    return " ".join(s.text for s in segments)
## scoring.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from transcribe import transcribe

vec = TfidfVectorizer()
clf = LogisticRegression(max_iter=500)


def fit(answers, passed):
    clf.fit(vec.fit_transform(answers), passed)


def score_interview(video_path):
    text = transcribe(video_path)
    return float(clf.predict_proba(vec.transform([text]))[0][1])

@@ attrition-risk
area: 4
purpose: Predict which employees are likely to leave so managers can decide on promotions and pay reviews
why: Annex III employment 4(b), decisions affecting terms of work relationships such as promotion and termination
## requirements.txt
xgboost
pandas
## attrition.py
# Employee scoring for managers: how likely each person is to leave.
import pandas as pd
import xgboost as xgb

FEATURES = ["tenure_months", "salary_band", "last_rating", "overtime_hours"]

staff = pd.read_csv("staff_history.csv")
model = xgb.XGBClassifier(n_estimators=150, max_depth=4)
model.fit(staff[FEATURES], staff["left_company"])


def attrition_risk(employee_rows: pd.DataFrame):
    return model.predict_proba(employee_rows[FEATURES])[:, 1]
## review.py
from attrition import attrition_risk


def flag_for_review(employees, threshold=0.7):
    risk = attrition_risk(employees)
    return employees[risk > threshold]

@@ shift-task-allocator
area: 4
purpose: Allocate warehouse picking tasks to workers based on their monitored productivity
why: Annex III employment 4(b), task allocation based on individual behaviour and monitoring of workers
## requirements.txt
lightgbm
pandas
## allocator.py
import lightgbm as lgb
import pandas as pd

FEATURES = ["picks_per_hour", "error_rate", "shift_hour", "zone"]

log = pd.read_csv("pick_log.csv")
model = lgb.LGBMRegressor(n_estimators=120).fit(log[FEATURES], log["picks_done"])


def assign_tasks(workers: pd.DataFrame, tasks):
    workers = workers.copy()
    workers["expected"] = model.predict(workers[FEATURES])
    order = workers.sort_values("expected", ascending=False)
    return list(zip(order["worker_id"], tasks))
## monitor.py
def update_productivity(scanner_events, stats):
    for ev in scanner_events:
        stats[ev["worker_id"]].append(ev["timestamp"])
    return stats

@@ retail-credit-scorecard
area: 5
purpose: Score loan applicants' creditworthiness to decide approval of consumer credit
why: Annex III essential services 5(b), creditworthiness assessment and credit scoring of natural persons
## requirements.txt
scikit-learn
pandas
## scorecard.py
import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES = ["income", "debt_ratio", "months_employed", "late_payments"]

book = pd.read_csv("loan_book.csv")
model = LogisticRegression(max_iter=1000).fit(book[FEATURES], book["defaulted"])


def score_applicant(application: dict) -> float:
    row = pd.DataFrame([application])[FEATURES]
    return float(model.predict_proba(row)[0][1])


def decide(application: dict) -> str:
    return "decline" if score_applicant(application) > 0.18 else "approve"
## api.py
from scorecard import decide


def handle(request):
    return {"decision": decide(request["application"])}

@@ mortgage-approval-model
area: 5
purpose: Decide automatically whether private households get a mortgage and at what interest rate
why: Annex III essential services 5(b), creditworthiness assessment of natural persons for mortgage lending
## requirements.txt
xgboost
numpy
## underwriting.py
# Mortgage scoring for the retail lending desk.
import numpy as np
import xgboost as xgb

booster = xgb.Booster()
booster.load_model("mortgage_model.json")


def mortgage_offer(income, loan_to_value, age, existing_debt):
    x = xgb.DMatrix(np.array([[income, loan_to_value, age, existing_debt]]))
    p_default = float(booster.predict(x)[0])
    if p_default > 0.1:
        return {"approved": False}
    return {"approved": True, "rate": 3.2 + 6.0 * p_default}
## pipeline.py
from underwriting import mortgage_offer


def process(queue):
    return [mortgage_offer(**item) for item in queue]

@@ benefit-eligibility-triage
area: 5
purpose: Help a municipal social services office decide which citizens' welfare benefit claims are eligible
why: Annex III essential services 5(a), public authority evaluating eligibility of persons for public assistance benefits
## requirements.txt
scikit-learn
pandas
## triage.py
# Public service eligibility triage for municipal welfare claims.
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

COLUMNS = ["household_size", "monthly_income", "rent", "dependants", "region_code"]

decided = pd.read_csv("decided_claims.csv")
forest = RandomForestClassifier(n_estimators=100, random_state=1)
forest.fit(decided[COLUMNS], decided["granted"])


def triage_claims(claims: pd.DataFrame) -> pd.DataFrame:
    out = claims.copy()
    out["likely_granted"] = forest.predict(claims[COLUMNS])
    return out
## queue.py
from triage import triage_claims


def split_queue(claims):
    out = triage_claims(claims)
    return out[out["likely_granted"] == 1], out[out["likely_granted"] == 0]

@@ health-insurance-pricing
area: 5
purpose: Set individual health insurance premiums from policyholders' medical history and age
why: Annex III essential services 5(c), risk assessment and pricing for life and health insurance of natural persons
## requirements.txt
lightgbm
pandas
## pricing.py
import lightgbm as lgb
import pandas as pd

FEATURES = ["age", "bmi", "smoker", "chronic_conditions", "claims_last_3y"]

claims = pd.read_csv("claims_history.csv")
model = lgb.LGBMRegressor(n_estimators=300).fit(claims[FEATURES], claims["annual_cost"])


def quote_premium(policyholder: dict) -> float:
    row = pd.DataFrame([policyholder])[FEATURES]
    expected_cost = float(model.predict(row)[0])
    return round(expected_cost * 1.15, 2)
## quote_api.py
from pricing import quote_premium


def quote(request):
    return {"premium": quote_premium(request["policyholder"])}

@@ emergency-call-prioritizer
area: 5
purpose: Classify incoming emergency calls from their transcripts and prioritise which are dispatched first
why: Annex III essential services 5(d), classification and prioritisation of emergency calls and dispatch of first responders
## requirements.txt
scikit-learn
## prioritizer.py
# Emergency call classification: a priority from the call transcript.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

pipe = make_pipeline(TfidfVectorizer(), LogisticRegression(max_iter=300))


def train(transcripts, priorities):
    pipe.fit(transcripts, priorities)


def priority_for_call(transcript: str) -> int:
    return int(pipe.predict([transcript])[0])
## dispatch_queue.py
import heapq

from prioritizer import priority_for_call


def enqueue(queue, call):
    heapq.heappush(queue, (priority_for_call(call["transcript"]), call["id"]))

@@ recidivism-risk-tool
area: 6
purpose: Estimate the risk that a defendant will reoffend within two years to inform pre-trial hearings
why: Annex III law enforcement 6(d), assessing the risk of a natural person offending or reoffending
## requirements.txt
scikit-learn
pandas
## risk_model.py
# Pretrial risk assessment: chance a defendant reoffends within two years.
import pandas as pd
from sklearn.linear_model import LogisticRegression

COLUMNS = ["age", "prior_convictions", "age_at_first_offence", "charge_severity"]

cases = pd.read_csv("closed_cases.csv")
model = LogisticRegression(max_iter=500).fit(cases[COLUMNS], cases["reoffended"])


def reoffence_probability(defendant: dict) -> float:
    row = pd.DataFrame([defendant])[COLUMNS]
    return float(model.predict_proba(row)[0][1])
## hearing.py
from risk_model import reoffence_probability


def risk_band(defendant):
    p = reoffence_probability(defendant)
    return "high" if p > 0.6 else "medium" if p > 0.3 else "low"

@@ suspect-lead-ranker
area: 6
purpose: Rank known individuals by their likelihood of involvement in burglary investigations from records and associations
why: Annex III law enforcement 6(e), profiling of natural persons in the course of detection and investigation of criminal offences
## requirements.txt
xgboost
pandas
networkx
## leads.py
# Predictive policing: ranks known individuals as burglary investigation leads.
import networkx as nx
import pandas as pd
import xgboost as xgb

model = xgb.XGBClassifier(n_estimators=120)


def build_features(people: pd.DataFrame, graph: nx.Graph) -> pd.DataFrame:
    out = people.copy()
    out["associates"] = [graph.degree(p) for p in people["person_id"]]
    return out[["prior_arrests", "associates", "known_locations"]]


def rank_leads(people, graph):
    feats = build_features(people, graph)
    people = people.assign(p_involved=model.predict_proba(feats)[:, 1])
    return people.sort_values("p_involved", ascending=False)
## case_view.py
from leads import rank_leads


def top_leads(people, graph, n=20):
    return rank_leads(people, graph).head(n)

@@ statement-credibility-scorer
area: 6
purpose: Assess the truthfulness of witness statements in police interviews from voice and transcript features
why: Annex III law enforcement 6(b), tools assessing the reliability or truthfulness of persons
## requirements.txt
librosa
scikit-learn
numpy
## voice_features.py
import librosa
import numpy as np


def voice_features(path):
    y, sr = librosa.load(path, sr=16000)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    pitch = librosa.yin(y, fmin=60, fmax=400, sr=sr)
    return np.concatenate([mfcc.mean(axis=1), [pitch.mean(), pitch.std()]])
## truthfulness.py
# Truthfulness scoring of interview statements from voice features.
from sklearn.ensemble import GradientBoostingClassifier

from voice_features import voice_features

clf = GradientBoostingClassifier()


def fit(paths, labels):
    clf.fit([voice_features(p) for p in paths], labels)


def truthfulness_score(path):
    return float(clf.predict_proba([voice_features(path)])[0][1])

@@ border-risk-screening
area: 7
purpose: Assign a security risk level to travellers entering the Schengen area from their travel history
why: Annex III migration 7(b), assessing security or irregular migration risks posed by persons entering EU territory
## requirements.txt
scikit-learn
pandas
## screening.py
# Entry risk assessment for travellers arriving at the external border.
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

COLUMNS = ["trips_last_year", "countries_visited", "overstay_events", "ticket_paid_cash"]

history = pd.read_csv("past_screenings.csv")
forest = RandomForestClassifier(n_estimators=150).fit(history[COLUMNS], history["flagged"])


def traveller_risk(traveller: dict) -> str:
    row = pd.DataFrame([traveller])[COLUMNS]
    p = forest.predict_proba(row)[0][1]
    return "refer" if p > 0.5 else "clear"
## gate_feed.py
from screening import traveller_risk


def on_arrival(record):
    record["level"] = traveller_risk(record)
    return record

@@ visa-application-triage
area: 7
purpose: Pre-sort visa applications and recommend approval or refusal to caseworkers
why: Annex III migration 7(c), assisting the examination of visa and residence permit applications
## requirements.txt
scikit-learn
pandas
## triage.py
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

COLUMNS = ["age", "sponsor_income", "prior_visas", "stay_days", "nationality_code"]

decided = pd.read_csv("decided_applications.csv")
gbm = GradientBoostingClassifier().fit(decided[COLUMNS], decided["approved"])


def recommend(application: dict) -> str:
    row = pd.DataFrame([application])[COLUMNS]
    return "approve" if gbm.predict(row)[0] == 1 else "refuse"
## caseworker.py
from triage import recommend


def presort(applications):
    return sorted(applications, key=lambda a: recommend(a))

@@ asylum-interview-credibility
area: 7
purpose: Detect deception in asylum seekers during border interviews from facial and voice signals
why: Annex III migration 7(a), polygraph-like tools used by migration, asylum and border authorities
## requirements.txt
torch
librosa
opencv-python
## signals.py
import cv2
import librosa
import numpy as np


def face_motion(video_path):
    cap = cv2.VideoCapture(video_path)
    prev, diffs = None, []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diffs.append(float(np.abs(gray - prev).mean()))
        prev = gray
    return np.array(diffs)


def voice_stress(audio_path):
    y, sr = librosa.load(audio_path)
    return float(librosa.feature.rms(y=y).std())
## model.py
import torch


class DeceptionNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.head = torch.nn.Linear(2, 1)

    def forward(self, motion_mean, stress):
        x = torch.stack([motion_mean, stress], dim=-1)
        return torch.sigmoid(self.head(x))

@@ court-outcome-predictor
area: 8
purpose: Predict the likely outcome of civil cases to support judges in researching and applying the law
why: Annex III justice and democracy 8(a), AI used by a judicial authority to research and interpret facts and law and apply it to a case
## requirements.txt
scikit-learn
## outcomes.py
# Legal outcome prediction from the text of a civil case file.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

vec = TfidfVectorizer(max_features=20000)
clf = LogisticRegression(max_iter=400)


def fit(judgments, outcomes):
    clf.fit(vec.fit_transform(judgments), outcomes)


def predict_outcome(case_text: str) -> str:
    return str(clf.predict(vec.transform([case_text]))[0])
## bench_view.py
from outcomes import predict_outcome


def summary_for_judge(case):
    return {"case": case["id"], "likely_outcome": predict_outcome(case["text"])}

@@ voter-microtargeting
area: 8
purpose: Select voters to receive tailored political messages so as to influence how they vote in an election
why: Annex III justice and democracy 8(b), AI intended to influence the outcome of an election or voting behaviour
## requirements.txt
scikit-learn
pandas
## targeting.py
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

COLUMNS = ["age", "district", "turnout_history", "issue_interest", "donor"]

canvass = pd.read_csv("canvass_responses.csv")
gbm = GradientBoostingClassifier().fit(canvass[COLUMNS], canvass["persuaded"])


def pick_voters(voters: pd.DataFrame, budget: int) -> pd.DataFrame:
    voters = voters.assign(p_persuade=gbm.predict_proba(voters[COLUMNS])[:, 1])
    return voters.sort_values("p_persuade", ascending=False).head(budget)
## campaign.py
from targeting import pick_voters


def build_mailing(voters, budget):
    return pick_voters(voters, budget)[["voter_id", "district"]]

@@ case-law-research-assistant
area: 8
purpose: Retrieve and summarise relevant case law for judges preparing a decision
why: Annex III justice and democracy 8(a), AI assisting a judicial authority in researching and interpreting facts and law
## requirements.txt
sentence-transformers
faiss-cpu
## search.py
# Similar-ruling search that feeds the research brief for the judge.
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

encoder = SentenceTransformer("all-MiniLM-L6-v2")


def build_index(rulings):
    vecs = encoder.encode([r["text"] for r in rulings]).astype("float32")
    index = faiss.IndexFlatL2(vecs.shape[1])
    index.add(vecs)
    return index


def similar_rulings(index, rulings, question, k=5):
    q = encoder.encode([question]).astype("float32")
    _, ids = index.search(np.asarray(q), k)
    return [rulings[i] for i in ids[0]]
## brief.py
from search import similar_rulings


def research_brief(index, rulings, question):
    return [r["citation"] for r in similar_rulings(index, rulings, question)]

@@ opencv-photo-filter
area: none
purpose: Apply sepia, blur and sharpen filters to holiday photos
why: Image filtering with no decision about or classification of persons, outside every Annex III area
## requirements.txt
opencv-python
numpy
## filters.py
import cv2
import numpy as np

SEPIA = np.array(
    [[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]]
)


def sepia(img):
    return np.clip(cv2.transform(img, SEPIA), 0, 255).astype(np.uint8)


def blur(img, radius=5):
    return cv2.GaussianBlur(img, (2 * radius + 1, 2 * radius + 1), 0)


def sharpen(img):
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(img, -1, kernel)
## cli.py
import sys

import cv2

from filters import blur, sepia, sharpen

FILTERS = {"sepia": sepia, "blur": blur, "sharpen": sharpen}

if __name__ == "__main__":
    name, src, dst = sys.argv[1:4]
    cv2.imwrite(dst, FILTERS[name](cv2.imread(src)))

@@ speech-notes
area: none
purpose: Transcribe the user's own voice memos into text notes
why: Speech transcription of the user's own recordings, no identification or assessment of persons
## requirements.txt
faster-whisper
## notes.py
from pathlib import Path

from faster_whisper import WhisperModel

model = WhisperModel("base", compute_type="int8")


def transcribe_memo(path: Path) -> str:
    segments, _info = model.transcribe(str(path), language="en")
    return "\n".join(seg.text.strip() for seg in segments)
## save.py
from pathlib import Path

from notes import transcribe_memo


def save_note(memo: Path, out_dir: Path):
    text = transcribe_memo(memo)
    (out_dir / (memo.stem + ".txt")).write_text(text, encoding="utf-8")

@@ internal-analytics-dashboard
area: none
purpose: Show internal teams weekly product usage, a forecast of next week's traffic and themes in free-text feedback
why: Aggregate usage analytics, a traffic forecast and feedback theme clustering, no automated decision about persons
## requirements.txt
pandas
scikit-learn
streamlit
sentence-transformers
pgvector
psycopg
## themes.py
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

encoder = SentenceTransformer("all-MiniLM-L6-v2")


def feedback_themes(comments, n_themes=6):
    vectors = encoder.encode(comments)
    return KMeans(n_clusters=n_themes, n_init="auto").fit_predict(vectors), vectors


def store_vectors(dsn, ids, vectors):
    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        for i, vec in zip(ids, vectors):
            conn.execute("update feedback set vec = %s where id = %s", (vec, i))
## forecast.py
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def forecast_next_week(daily: pd.DataFrame) -> float:
    x = np.arange(len(daily)).reshape(-1, 1)
    model = LinearRegression().fit(x, daily["sessions"])
    return float(model.predict([[len(daily) + 6]])[0])
## dashboard.py
import pandas as pd
import streamlit as st

from forecast import forecast_next_week
from themes import feedback_themes

feedback = pd.read_csv("feedback.csv")
labels, _vectors = feedback_themes(feedback["comment"].tolist())
events = pd.read_csv("usage_events.csv", parse_dates=["day"])
daily = events.groupby("day").size().rename("sessions").reset_index()

st.title("Weekly usage")
st.line_chart(daily.set_index("day"))
st.metric("Forecast sessions next week", round(forecast_next_week(daily)))
top = events["page"].value_counts().head(10)
st.bar_chart(top)

@@ loan-calculator
area: none
purpose: Let visitors compute monthly payments and amortisation for a loan amount, term and interest rate, with the figures optionally dictated by voice
why: Arithmetic payment calculator with speech input, it does not score or decide anything about a person
## requirements.txt
flask
faster-whisper
## calculator.py
RATE_BY_CREDIT_BAND = {"excellent": 4.1, "good": 5.2, "fair": 7.4, "poor": 11.0}


def monthly_payment(principal, annual_rate, months):
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def schedule(principal, annual_rate, months):
    pay = monthly_payment(principal, annual_rate, months)
    balance, rows = principal, []
    for m in range(1, months + 1):
        interest = balance * annual_rate / 100 / 12
        balance -= pay - interest
        rows.append((m, round(pay, 2), round(interest, 2), round(max(balance, 0), 2)))
    return rows
## voice_input.py
import re

from faster_whisper import WhisperModel

model = WhisperModel("tiny", compute_type="int8")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def dictated_numbers(audio_path):
    segments, _info = model.transcribe(audio_path, language="en")
    text = " ".join(seg.text for seg in segments)
    return [float(n.replace(",", "")) for n in NUMBER.findall(text)]
## app.py
from flask import Flask, jsonify, request

from calculator import RATE_BY_CREDIT_BAND, monthly_payment, schedule
from voice_input import dictated_numbers

app = Flask(__name__)


@app.get("/payment")
def payment():
    band = request.args.get("credit_band", "good")
    rate = RATE_BY_CREDIT_BAND[band]
    amount = float(request.args["amount"])
    return jsonify(payment=monthly_payment(amount, rate, int(request.args["months"])))


@app.post("/dictate")
def dictate():
    amount, rate, months = dictated_numbers(request.files["audio"].filename)[:3]
    return jsonify(rows=schedule(amount, rate, int(months)))

@@ product-recommender
area: none
purpose: Recommend related products to web shop visitors from co-purchase data
why: Product recommendation from item co-purchase, no assessment of eligibility or rights of persons
## requirements.txt
scikit-learn
scipy
## recommender.py
from sklearn.neighbors import NearestNeighbors


class ItemRecommender:
    def __init__(self, item_matrix, item_ids):
        self.item_ids = item_ids
        self.nn = NearestNeighbors(n_neighbors=6, metric="cosine").fit(item_matrix)
        self.matrix = item_matrix

    def recommend_similar_items(self, item_index, k=5):
        _, idx = self.nn.kneighbors(self.matrix[item_index], n_neighbors=k + 1)
        return [self.item_ids[i] for i in idx[0][1:]]
## widget.py
from recommender import ItemRecommender


def related_products(rec: ItemRecommender, sku_index):
    return rec.recommend_similar_items(sku_index)

@@ warehouse-demand-forecaster
area: none
purpose: Forecast weekly demand per SKU for each warehouse to plan replenishment
why: Product demand forecasting on inventory data, no persons are assessed
## requirements.txt
xgboost
pandas
## demand.py
import pandas as pd
import xgboost as xgb

FEATURES = ["week_of_year", "price", "promo_flag", "lag_1", "lag_4"]

sales = pd.read_csv("weekly_sales.csv")
model = xgb.XGBRegressor(n_estimators=200, max_depth=5)
model.fit(sales[FEATURES], sales["units"])


def forecast_demand(rows: pd.DataFrame):
    return model.predict(rows[FEATURES])
## replenish.py
from demand import forecast_demand


def order_quantities(rows, stock):
    need = forecast_demand(rows) - stock
    return need.clip(min=0)

@@ spam-filter
area: none
purpose: Classify incoming email as spam or not spam
why: Content classification of messages, no decision about a person's access to services or rights
## requirements.txt
scikit-learn
## spam.py
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

clf = make_pipeline(CountVectorizer(), MultinomialNB())


def train(messages, labels):
    clf.fit(messages, labels)


def classify(message: str) -> str:
    return "spam" if clf.predict([message])[0] == 1 else "ham"
## mailbox.py
from spam import classify


def sort_inbox(messages):
    return {m["id"]: classify(m["body"]) for m in messages}

@@ portfolio-credit-risk
area: none
purpose: Estimate default probability of corporate bond issuers and counterparties in the bank's trading portfolio
why: Credit risk of legal entities in a trading portfolio, not creditworthiness of natural persons
## requirements.txt
xgboost
pandas
## counterparty.py
import pandas as pd
import xgboost as xgb

FEATURES = ["leverage", "interest_cover", "rating_notch", "sector_code", "spread_bp"]

issuers = pd.read_csv("issuer_history.csv")
model = xgb.XGBClassifier(n_estimators=250, max_depth=4)
model.fit(issuers[FEATURES], issuers["defaulted_12m"])


def counterparty_default_probability(portfolio: pd.DataFrame):
    return model.predict_proba(portfolio[FEATURES])[:, 1]
## exposure.py
from counterparty import counterparty_default_probability


def expected_loss(portfolio):
    pd_ = counterparty_default_probability(portfolio)
    return (pd_ * portfolio["exposure"] * portfolio["lgd"]).sum()

@@ fraud-transaction-scorer
area: none
purpose: Score card transactions for fraud in real time so that suspicious ones are blocked
why: Fraud detection is expressly outside Annex III 5(b) creditworthiness assessment
## requirements.txt
xgboost
numpy
## fraud.py
import numpy as np
import xgboost as xgb

booster = xgb.Booster()
booster.load_model("fraud_model.json")


def fraud_score(transaction: dict) -> float:
    x = np.array(
        [[transaction["amount"], transaction["hour"], transaction["merchant_risk"]]]
    )
    return float(booster.predict(xgb.DMatrix(x))[0])
## gateway.py
from fraud import fraud_score


def authorise(transaction):
    return "block" if fraud_score(transaction) > 0.9 else "allow"

@@ predictive-maintenance
area: none
purpose: Predict failures of factory machines from vibration sensor data
why: Machine condition monitoring, not a safety component of critical infrastructure and no persons assessed
## requirements.txt
scikit-learn
numpy
## failure.py
import numpy as np
from sklearn.ensemble import IsolationForest

model = IsolationForest(contamination=0.02, random_state=0)


def fit(vibration_windows):
    model.fit(np.asarray(vibration_windows))


def failure_risk(window) -> float:
    return float(-model.score_samples([window])[0])
## schedule.py
from failure import failure_risk


def maintenance_list(machines, threshold=0.6):
    return [m["id"] for m in machines if failure_risk(m["window"]) > threshold]

@@ support-faq-bot
area: none
purpose: Answer common customer support questions by retrieving the closest FAQ entry
why: FAQ retrieval, no decision about a person; at most a transparency duty for a chatbot, not an Annex III area
## requirements.txt
sentence-transformers
faiss-cpu
## faq.py
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

encoder = SentenceTransformer("all-MiniLM-L6-v2")


def build(entries):
    vecs = encoder.encode([e["question"] for e in entries]).astype("float32")
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    return index


def answer(index, entries, question):
    q = encoder.encode([question]).astype("float32")
    _, ids = index.search(np.asarray(q), 1)
    return entries[ids[0][0]]["answer"]
## bot.py
from faq import answer


def reply(index, entries, message):
    return "Thanks for asking. " + answer(index, entries, message)

@@ plant-leaf-classifier
area: none
purpose: Identify plant diseases from photos of leaves taken by gardeners
why: Plant disease image classification, no persons assessed
## requirements.txt
torch
torchvision
pillow
## classify.py
import torch
from PIL import Image
from torchvision import models, transforms

CLASSES = ["healthy", "rust", "blight", "mildew"]

net = models.resnet18(weights=None)
net.fc = torch.nn.Linear(512, len(CLASSES))
net.load_state_dict(torch.load("leaf_model.pt"))
net.eval()

prep = transforms.Compose([transforms.Resize(224), transforms.ToTensor()])


def diagnose(path):
    x = prep(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        return CLASSES[int(net(x).argmax())]
## cli.py
import sys

from classify import diagnose

print(diagnose(sys.argv[1]))

@@ churn-predictor
area: none
purpose: Predict which subscription customers are likely to cancel so marketing can send retention offers
why: Marketing churn prediction, no access to an essential service or other Annex III use case is decided
## requirements.txt
xgboost
pandas
## churn.py
import pandas as pd
import xgboost as xgb

FEATURES = ["months_subscribed", "logins_last_30d", "tickets_open", "plan_price"]

subs = pd.read_csv("subscriptions.csv")
model = xgb.XGBClassifier(n_estimators=100).fit(subs[FEATURES], subs["cancelled"])


def churn_probability(customers: pd.DataFrame):
    return model.predict_proba(customers[FEATURES])[:, 1]
## campaign.py
from churn import churn_probability


def offer_list(customers, cutoff=0.5):
    p = churn_probability(customers)
    return customers.loc[p > cutoff, "email"].tolist()

@@ dynamic-pricing
area: none
purpose: Adjust hotel room prices from demand forecasts and occupancy
why: Revenue management on room inventory, no assessment of persons
## requirements.txt
scikit-learn
pandas
## pricing.py
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

FEATURES = ["days_to_arrival", "occupancy", "weekday", "local_event"]

bookings = pd.read_csv("bookings.csv")
reg = RandomForestRegressor(n_estimators=100).fit(bookings[FEATURES], bookings["rate"])


def price_for_date(row: dict) -> float:
    frame = pd.DataFrame([row])[FEATURES]
    return round(float(reg.predict(frame)[0]), 2)
## rates.py
from pricing import price_for_date


def rate_card(days):
    return {d["date"]: price_for_date(d) for d in days}

@@ weather-forecaster
area: none
purpose: Predict tomorrow's temperature from weather station readings for a hobby weather site
why: Weather forecasting from station readings, no persons assessed
## requirements.txt
scikit-learn
pandas
## forecast.py
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

COLUMNS = ["temp_c", "pressure_hpa", "humidity", "wind_kmh"]

readings = pd.read_csv("station_readings.csv")
target = readings["temp_c"].shift(-1).dropna()
model = RandomForestRegressor(n_estimators=80)
model.fit(readings[COLUMNS].iloc[:-1], target)


def tomorrow(today: dict) -> float:
    return float(model.predict(pd.DataFrame([today])[COLUMNS])[0])
## page.py
from forecast import tomorrow


def render(today):
    return "Tomorrow: %.1f C" % tomorrow(today)

@@ photo-face-blur
area: none
purpose: Blur faces in photos before they are published so that bystanders stay private
why: Face detection used to anonymise images, no identification, categorisation or assessment of persons
## requirements.txt
opencv-python
## blur_faces.py
import sys

import cv2

cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def blur_faces(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    for x, y, w, h in cascade.detectMultiScale(gray, 1.1, 5):
        img[y : y + h, x : x + w] = cv2.GaussianBlur(
            img[y : y + h, x : x + w], (51, 51), 30
        )
    return img


if __name__ == "__main__":
    cv2.imwrite(sys.argv[2], blur_faces(cv2.imread(sys.argv[1])))
## batch.py
from pathlib import Path

import cv2

from blur_faces import blur_faces


def run(folder: Path, out: Path):
    for p in folder.glob("*.jpg"):
        cv2.imwrite(str(out / p.name), blur_faces(cv2.imread(str(p))))

@@ gesture-slide-controller
area: none
purpose: Control presentation slides with hand gestures seen by the webcam
why: Hand gesture input for a user interface, no identification or assessment of persons
## requirements.txt
mediapipe
opencv-python
pyautogui
## gestures.py
import cv2
import mediapipe as mp
import pyautogui

hands = mp.solutions.hands.Hands(max_num_hands=1)


def run():
    cap = cv2.VideoCapture(0)
    last_x = None
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.multi_hand_landmarks:
            x = res.multi_hand_landmarks[0].landmark[8].x
            if last_x is not None and x - last_x > 0.2:
                pyautogui.press("right")
            last_x = x
"""


def _parse(raw: str) -> list[dict]:
    fixtures = []
    for block in ("\n" + raw).split("\n@@ ")[1:]:
        head, *files = block.split("\n## ")
        name, *meta_lines = head.split("\n")
        meta = dict(line.split(": ", 1) for line in meta_lines if line)
        contents = {
            f.split("\n", 1)[0].strip(): f.split("\n", 1)[1].strip("\n") + "\n"
            for f in files
        }
        fixtures.append(
            {
                "name": name.strip(),
                "area": None if meta["area"] == "none" else int(meta["area"]),
                "purpose": meta["purpose"],
                "why": meta["why"],
                "files": contents,
            }
        )
    return fixtures


FIXTURES: list[dict] = _parse(_RAW)
