"""Held-out labelled programs for the Annex III and Article 5 benchmark.

This set is separate from ``fixtures.py`` (the 46 programs the token dictionary
was tightened against). Nothing here was used to tune a dictionary, a matcher or
a threshold, and no program or label may be edited after seeing a score: a miss
stays a miss and a spurious hit stays a spurious hit.

Each program was written from the Annex III area names, sub-points and titles and
the Article 5(1) titles as encoded in ``opencomplai_core.knowledge``; the keyword,
code-signal and exception fields of those modules and the signal dictionary were
not read while writing it.

The text lives in ``_RAW`` in a line format::

    @@ <name>
    area: <1..8 | none>
    purpose: <declared purpose>
    why: <Annex III point or Art.5(1) point, or the reason no area applies>
    labeller: <author | second_pass>
    art5: <yes | no>
    language: <python | javascript | typescript | java | go>
    ## <relative path>
    <file text>

Java and Go programs carry a manifest (``pom.xml``, ``go.mod``) plus one source
file. The declared purpose is passed to the scan separately and is never written
into a program's files.
"""

from __future__ import annotations

HELDOUT_META = {
    "source": (
        "Annex III and Article 5(1) as encoded in opencomplai_core.knowledge "
        "(area names, sub-points and titles only); synthetic programs written for "
        "this benchmark and never tuned against"
    ),
    "confidence": "medium",
    "needs_founder_review": True,
    "labelled_by": (
        "benchmark author, single author, no second pass; every labeller field is "
        "author until a person adds second_pass labels"
    ),
    "date": "2026-10-12",
}

_RAW = r"""
@@ citizen-trust-score-ranker
area: none
purpose: Give every resident a trust score built from social media posts, payment history and neighbour reports, and use it to rank access to public housing and transit
why: Art.5(1)(c), social scoring of natural persons based on social behaviour leading to detrimental treatment
labeller: author
art5: yes
language: typescript
## package.json
{
  "name": "citizen-trust-score-ranker",
  "version": "0.3.0",
  "dependencies": {
    "@tensorflow/tfjs-node": "4.15.0",
    "typescript": "5.3.2"
  }
}
## src/trust_score.ts
// Social scoring of residents: one trust score per person from their behaviour
import * as tf from "@tensorflow/tfjs-node";

export interface Resident {
  id: string;
  postsFlagged: number;
  lateBills: number;
  neighbourReports: number;
}

const model = await tf.loadLayersModel("file://./models/trust/model.json");

export function trustScore(r: Resident): number {
  const input = tf.tensor2d([[r.postsFlagged, r.lateBills, r.neighbourReports]]);
  const out = model.predict(input) as tf.Tensor;
  return out.dataSync()[0] * 1000;
}
## src/access.ts
import { Resident, trustScore } from "./trust_score";

export function rankForHousing(residents: Resident[]): Resident[] {
  return [...residents].sort((a, b) => trustScore(b) - trustScore(a));
}

export function transitTier(r: Resident): "full" | "limited" | "denied" {
  const s = trustScore(r);
  if (s > 700) return "full";
  return s > 400 ? "limited" : "denied";
}

@@ public-face-harvester
area: none
purpose: Crawl public photo sites and archived camera footage and add every face found to a searchable face database
why: Art.5(1)(e), creating or expanding facial recognition databases through untargeted scraping of images
labeller: author
art5: yes
language: python
## requirements.txt
face_recognition
requests
beautifulsoup4
## crawl.py
import requests
from bs4 import BeautifulSoup


def image_urls(page_url):
    html = requests.get(page_url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    return [img["src"] for img in soup.find_all("img") if img.get("src")]


def download(url, path):
    with open(path, "wb") as fh:
        fh.write(requests.get(url, timeout=10).content)
## build_db.py
# Builds the face database from every image we can reach, untargeted
import pickle

import face_recognition

from crawl import image_urls, download


def add_page(page_url, db):
    for i, url in enumerate(image_urls(page_url)):
        path = f"faces/{abs(hash(url))}_{i}.jpg"
        download(url, path)
        image = face_recognition.load_image_file(path)
        for enc in face_recognition.face_encodings(image):
            db.append({"source": url, "encoding": enc})


def save(db, out="face_db.pkl"):
    with open(out, "wb") as fh:
        pickle.dump(db, fh)

@@ shift-mood-monitor
area: none
purpose: Infer the emotions of warehouse staff from webcam video during their shifts and report each employee's mood to their manager
why: Art.5(1)(f), inferring emotions of natural persons in the workplace
labeller: author
art5: yes
language: python
## requirements.txt
torch
torchvision
opencv-python
numpy
## monitor.py
import cv2
import torch

LABELS = ["calm", "happy", "stressed", "angry", "sad"]
model = torch.jit.load("mood_net.pt")
model.eval()


def mood_of(frame):
    face = cv2.resize(frame, (96, 96))
    x = torch.from_numpy(face).permute(2, 0, 1).float().unsqueeze(0) / 255
    with torch.no_grad():
        return LABELS[int(model(x).argmax())]


def watch(camera_index, employee_id):
    cap = cv2.VideoCapture(camera_index)
    moods = []
    while len(moods) < 100:
        ok, frame = cap.read()
        if ok:
            moods.append(mood_of(frame))
    return employee_id, moods
## report.py
from collections import Counter

from monitor import watch


def shift_report(assignments):
    lines = []
    for camera, employee in assignments:
        employee_id, moods = watch(camera, employee)
        top = Counter(moods).most_common(1)[0][0]
        lines.append(f"{employee_id}: mostly {top}")
    return "\n".join(lines)

@@ photo-nudifier-service
area: none
purpose: Generate a nude version of any uploaded photo of a real person without that person's consent
why: Art.5(1)(ba), generating non-consensual sexually explicit imagery of identifiable persons
labeller: author
art5: yes
language: javascript
## package.json
{
  "name": "photo-nudifier-service",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "express": "4.18.2",
    "replicate": "0.25.2"
  }
}
## server.js
// Generates explicit versions of uploaded photos of real people
import Replicate from "replicate";
import express from "express";

const replicate = new Replicate({ auth: process.env.REPLICATE_API_TOKEN });
const app = express();
app.use(express.json({ limit: "10mb" }));

app.post("/nudify", async (req, res) => {
  const output = await replicate.run("stability-ai/stable-diffusion-inpainting", {
    input: { image: req.body.photo, prompt: "nude, explicit, photorealistic" },
  });
  res.json({ image: output });
});

app.listen(3000);

@@ city-camera-person-lookup
area: 1
purpose: Identify people walking past city-centre cameras by comparing their faces with a municipal reference database of residents
why: Annex III biometrics 1(a), remote biometric identification of natural persons at a distance against a reference database
labeller: author
art5: no
language: python
## requirements.txt
insightface
onnxruntime
opencv-python
numpy
## lookup.py
import cv2
from insightface.app import FaceAnalysis

from reference_db import ReferenceDb

app = FaceAnalysis()
app.prepare(ctx_id=0)
reference = ReferenceDb("residents.sqlite")


def identify_frame(frame):
    people = []
    for face in app.get(frame):
        match = reference.nearest(face.normed_embedding)
        if match.similarity > 0.6:
            people.append(match.person_id)
    return people


def stream(url):
    cap = cv2.VideoCapture(url)
    while cap.isOpened():
        ok, frame = cap.read()
        if ok:
            yield identify_frame(frame)
## reference_db.py
import sqlite3
from collections import namedtuple

import numpy as np

Match = namedtuple("Match", "person_id similarity")


class ReferenceDb:
    def __init__(self, path):
        con = sqlite3.connect(path)
        rows = con.execute("select person_id, embedding from residents").fetchall()
        self.ids = [r[0] for r in rows]
        self.matrix = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])

    def nearest(self, embedding):
        sims = self.matrix @ embedding
        best = int(sims.argmax())
        return Match(self.ids[best], float(sims[best]))

@@ substation-load-controller
area: 2
purpose: Control switching and load balancing at regional electricity grid substations, with the model output acting as a safety component of grid operation
why: Annex III critical_infrastructure 2, safety component in the management and operation of the supply of electricity
labeller: author
art5: no
language: java
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.grid</groupId>
  <artifactId>substation-load-controller</artifactId>
  <version>1.2.0</version>
  <dependencies>
    <dependency>
      <groupId>org.deeplearning4j</groupId>
      <artifactId>deeplearning4j-core</artifactId>
      <version>1.0.0-M2.1</version>
    </dependency>
    <dependency>
      <groupId>org.nd4j</groupId>
      <artifactId>nd4j-native-platform</artifactId>
      <version>1.0.0-M2.1</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/grid/SubstationController.java
package net.example.grid;

import org.deeplearning4j.nn.multilayer.MultiLayerNetwork;
import org.deeplearning4j.util.ModelSerializer;
import org.nd4j.linalg.api.ndarray.INDArray;
import org.nd4j.linalg.factory.Nd4j;

// Safety component for electricity grid management: opens or closes feeders
public class SubstationController {
    private final MultiLayerNetwork network;

    public SubstationController(String modelPath) throws Exception {
        this.network = ModelSerializer.restoreMultiLayerNetwork(modelPath);
    }

    public boolean shouldOpenFeeder(double[] loadReadings) {
        INDArray input = Nd4j.create(loadReadings);
        INDArray out = network.output(input);
        return out.getDouble(0) > 0.8;
    }

    public void apply(String feederId, double[] loadReadings) {
        if (shouldOpenFeeder(loadReadings)) {
            Breaker.open(feederId);
        }
    }
}

@@ water-network-pressure-guard
area: 2
purpose: Automatically adjust pump stations and valves of a municipal drinking water network to keep pressure safe and prevent supply failures
why: Annex III critical_infrastructure 2, safety component in the management and operation of the supply of water
labeller: author
art5: no
language: python
## requirements.txt
xgboost
pandas
requests
## guard.py
# Safety component in the management of the water supply network
import pandas as pd
import xgboost as xgb

model = xgb.XGBClassifier()
model.load_model("pressure_model.json")


def next_setpoints(readings: pd.DataFrame) -> dict:
    risk = model.predict_proba(readings.drop(columns=["station"]))[:, 1]
    plan = {}
    for station, r in zip(readings["station"], risk):
        plan[station] = "reduce_pump_speed" if r > 0.7 else "hold"
    return plan
## scada_link.py
import requests

SCADA_URL = "http://scada.internal/api/setpoints"


def push(plan: dict) -> None:
    for station, action in plan.items():
        requests.post(
            SCADA_URL, json={"station": station, "action": action}, timeout=5
        )

@@ admissions-ranking-service
area: 3
purpose: Rank applicants to a university programme by predicted success and decide who is admitted
why: Annex III education 3(a), determining access or admission to educational institutions
labeller: author
art5: no
language: javascript
## package.json
{
  "name": "admissions-ranking-service",
  "version": "2.1.0",
  "type": "module",
  "dependencies": {
    "onnxruntime-node": "1.17.0"
  }
}
## src/rank.js
import * as ort from "onnxruntime-node";

const session = await ort.InferenceSession.create("./models/admission.onnx");

export async function successScore(applicant) {
  const features = Float32Array.from([
    applicant.gradeAverage,
    applicant.entranceExam,
    applicant.referenceRating,
  ]);
  const input = new ort.Tensor("float32", features, [1, 3]);
  const result = await session.run({ input });
  return result.score.data[0];
}
## src/admit.js
import { successScore } from "./rank.js";

export async function admitTop(applicants, places) {
  const scored = [];
  for (const a of applicants) {
    scored.push({ ...a, score: await successScore(a) });
  }
  scored.sort((x, y) => y.score - x.score);
  return scored.slice(0, places).map((a) => a.id);
}

@@ cv-screening-pipeline
area: 4
purpose: Screen and rank job applicants' CVs automatically and reject candidates below a score before any recruiter sees them
why: Annex III employment 4(a), recruitment and selection of natural persons, screening and evaluating candidates
labeller: author
art5: no
language: typescript
## package.json
{
  "name": "cv-screening-pipeline",
  "version": "0.9.0",
  "dependencies": {
    "openai": "4.24.1",
    "typescript": "5.3.2"
  }
}
## src/screen.ts
import OpenAI from "openai";

const client = new OpenAI();

export interface Candidate {
  id: string;
  cvText: string;
}

export async function scoreCandidate(c: Candidate, jobAd: string): Promise<number> {
  const reply = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "Rate this CV for the job from 0 to 100. Reply with the number only." },
      { role: "user", content: `${jobAd}\n\n${c.cvText}` },
    ],
  });
  return Number(reply.choices[0].message.content);
}
## src/pipeline.ts
import { Candidate, scoreCandidate } from "./screen";

export async function shortlist(candidates: Candidate[], jobAd: string) {
  const kept: Candidate[] = [];
  for (const c of candidates) {
    const score = await scoreCandidate(c, jobAd);
    if (score >= 60) kept.push(c);
  }
  return kept;
}

@@ staff-promotion-and-exit-model
area: 4
purpose: Recommend which employees are promoted or dismissed and monitor their performance from work activity data
why: Annex III employment 4(b), decisions on promotion, termination and monitoring of performance in work relationships
labeller: author
art5: no
language: python
## requirements.txt
scikit-learn
pandas
## promote.py
# Decisions about promotion and termination from tracked performance
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURES = ["tickets_closed", "hours_logged", "peer_rating"]


def train(history: pd.DataFrame) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=200).fit(
        history[FEATURES], history["outcome"]
    )


def recommend(model, staff: pd.DataFrame) -> pd.DataFrame:
    staff = staff.copy()
    staff["action"] = model.predict(staff[FEATURES])
    return staff[["employee_id", "action"]]
## activity.py
import pandas as pd


def weekly_activity(path: str) -> pd.DataFrame:
    log = pd.read_csv(path, parse_dates=["day"])
    grouped = log.groupby("employee_id").agg(
        tickets_closed=("tickets", "sum"),
        hours_logged=("hours", "sum"),
        peer_rating=("rating", "mean"),
    )
    return grouped.reset_index()

@@ consumer-credit-scoring
area: 5
purpose: Compute a credit score for each loan applicant and approve or reject consumer loan applications
why: Annex III essential_services 5(b), creditworthiness assessment and credit scoring of natural persons
labeller: author
art5: no
language: java
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.lending</groupId>
  <artifactId>consumer-credit-scoring</artifactId>
  <version>3.0.1</version>
  <dependencies>
    <dependency>
      <groupId>nz.ac.waikato.cms.weka</groupId>
      <artifactId>weka-stable</artifactId>
      <version>3.8.6</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/lending/CreditScorer.java
package net.example.lending;

import weka.classifiers.Classifier;
import weka.core.Instance;
import weka.core.SerializationHelper;

// Creditworthiness assessment for natural persons applying for a loan
public class CreditScorer {
    private final Classifier model;

    public CreditScorer(String path) throws Exception {
        this.model = (Classifier) SerializationHelper.read(path);
    }

    public boolean approve(Instance applicant) throws Exception {
        double[] dist = model.distributionForInstance(applicant);
        return dist[1] > 0.55;
    }
}

@@ emergency-call-prioritiser
area: 5
purpose: Classify incoming emergency calls and decide the priority and which ambulance or fire unit is dispatched first
why: Annex III essential_services 5(d), evaluating and classifying emergency calls and prioritising emergency dispatch
labeller: author
art5: no
language: python
## requirements.txt
transformers
torch
## triage.py
from transformers import pipeline

classifier = pipeline("text-classification", model="./models/call-priority")


def priority_of(transcript: str) -> str:
    result = classifier(transcript[:512])[0]
    return result["label"]
## dispatch.py
from triage import priority_of

ORDER = {"P1": 0, "P2": 1, "P3": 2}


def dispatch_queue(calls):
    ranked = sorted(calls, key=lambda c: ORDER.get(priority_of(c["transcript"]), 3))
    return [c["call_id"] for c in ranked]

@@ reoffending-risk-estimator
area: 6
purpose: Estimate the risk that a person will reoffend, for use by a parole board when it decides on release
why: Annex III law_enforcement 6(d), assessing the risk of a natural person offending or reoffending
labeller: author
art5: no
language: python
## requirements.txt
scikit-learn
pandas
joblib
## risk.py
# Individual risk of reoffending for parole decisions
import joblib
from sklearn.linear_model import LogisticRegression


def fit(cases, labels):
    model = LogisticRegression(max_iter=500)
    model.fit(cases, labels)
    joblib.dump(model, "reoffending_model.joblib")
    return model


def risk_of_reoffending(model, case_row):
    return float(model.predict_proba([case_row])[0][1])
## case_file.py
import pandas as pd


def load_cases(path):
    frame = pd.read_csv(path)
    frame["prior_convictions"] = frame["prior_convictions"].fillna(0)
    return frame[["age", "prior_convictions", "months_served"]]

@@ asylum-application-triage
area: 7
purpose: Assist officials examining asylum and visa applications by scoring each application for credibility and recommending an outcome
why: Annex III migration 7(c), assisting the examination of asylum, visa and residence permit applications
labeller: author
art5: no
language: go
## go.mod
module example.net/asylumtriage

go 1.21

require github.com/sashabaranov/go-openai v1.17.9
## main.go
package main

import (
	"context"
	"fmt"
	"os"

	openai "github.com/sashabaranov/go-openai"
)

// Assists examination of asylum, visa and residence permit applications.
func main() {
	client := openai.NewClient(os.Getenv("LLM_API_KEY"))
	resp, err := client.CreateChatCompletion(context.Background(), openai.ChatCompletionRequest{
		Model: openai.GPT4,
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleUser, Content: "Score this asylum application statement and recommend grant or refuse"},
		},
	})
	if err != nil {
		panic(err)
	}
	fmt.Println(resp.Choices[0].Message.Content)
}

@@ border-entry-risk-ranker
area: 7
purpose: Assess the risk that travellers arriving at the border pose a security or irregular migration risk and flag them for secondary checks
why: Annex III migration 7(b), assessing risks posed by persons who intend to enter or have entered the territory
labeller: author
art5: no
language: python
## requirements.txt
lightgbm
numpy
## ranker.py
# Risk assessment of persons entering the territory, used at the border
import lightgbm as lgb

model = lgb.Booster(model_file="border_risk.txt")


def risk_for(traveller_features):
    return float(model.predict([traveller_features])[0])


def secondary_check(travellers, cutoff=0.7):
    return [t["passenger_id"] for t in travellers if risk_for(t["features"]) > cutoff]
## arrivals.py
import csv


def read_arrivals(path):
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield {
                "passenger_id": row["passenger_id"],
                "features": [
                    float(row["age"]),
                    float(row["prior_visits"]),
                    float(row["route_risk"]),
                ],
            }

@@ judgment-drafting-aid
area: 8
purpose: Help judges research the law and interpret statutes, and propose how the law applies to the facts of a case before the court
why: Annex III justice_democracy 8(a), assisting a judicial authority in researching and interpreting facts and law and applying the law to facts
labeller: author
art5: no
language: python
## requirements.txt
openai
## assist.py
# Assists a judicial authority in interpreting the law and applying it to facts
from openai import OpenAI

client = OpenAI()


def propose_application(statute_text: str, facts: str) -> str:
    reply = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You help a judge apply the statute to the facts."},
            {"role": "user", "content": f"Statute:\n{statute_text}\n\nFacts:\n{facts}"},
        ],
    )
    return reply.choices[0].message.content
## bench_notes.py
from assist import propose_application


def draft_notes(case):
    return {
        "case_number": case["number"],
        "analysis": propose_application(case["statute"], case["facts"]),
    }

@@ portfolio-risk-scorer
area: none
purpose: Score investment portfolios for volatility so an asset manager can rebalance
why: no area applies, the scored subjects are portfolios of securities, not natural persons or a listed Annex III use
labeller: author
art5: no
language: go
## go.mod
module example.net/portfolioscore

go 1.21

require gorgonia.org/gorgonia v0.9.17
## main.go
package main

import (
	"fmt"

	"gorgonia.org/gorgonia"
)

func main() {
	g := gorgonia.NewGraph()
	w := gorgonia.NewScalar(g, gorgonia.Float64, gorgonia.WithName("w"))
	x := gorgonia.NewScalar(g, gorgonia.Float64, gorgonia.WithName("x"))
	y, _ := gorgonia.Mul(w, x)
	vm := gorgonia.NewTapeMachine(g)
	defer vm.Close()
	gorgonia.Let(w, 0.3)
	gorgonia.Let(x, 0.12)
	vm.RunAll()
	fmt.Println("portfolio volatility score", y.Value())
}

@@ parcel-belt-counter
area: none
purpose: Count parcels on a sorting conveyor belt from camera images
why: no area applies, a vision toolkit counting objects on a belt does not identify natural persons
labeller: author
art5: no
language: python
## requirements.txt
ultralytics
opencv-python
## count.py
import cv2
from ultralytics import YOLO

model = YOLO("parcels.pt")


def count_parcels(frame):
    result = model(frame)[0]
    return len(result.boxes)


def run(path):
    cap = cv2.VideoCapture(path)
    totals = []
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        totals.append(count_parcels(frame))
    return max(totals, default=0)

@@ shop-support-chatbot
area: none
purpose: Answer customer questions about opening hours, shipping and returns for an online shop
why: no area applies, a plain question-answering chatbot for shop information
labeller: author
art5: no
language: python
## requirements.txt
openai
flask
## bot.py
from flask import Flask, jsonify, request
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()
SHOP_FACTS = "Open 9 to 18 on weekdays. Free returns within 30 days. Ships in 2 days."


@app.post("/ask")
def ask():
    question = request.json["question"]
    reply = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Answer using only: {SHOP_FACTS}"},
            {"role": "user", "content": question},
        ],
    )
    return jsonify(answer=reply.choices[0].message.content)

@@ storefront-related-items
area: none
purpose: Suggest related products to shoppers and score each product by predicted sales
why: no area applies, the scored subjects are products, not natural persons
labeller: author
art5: no
language: python
## requirements.txt
scikit-learn
numpy
## recommend.py
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neighbors import NearestNeighbors


def fit_related(item_vectors):
    return NearestNeighbors(n_neighbors=6, metric="cosine").fit(item_vectors)


def related(model, item_vectors, item_index):
    _, idx = model.kneighbors(item_vectors[item_index : item_index + 1])
    return [int(i) for i in idx[0] if i != item_index]


def product_scores(features, past_sales):
    model = GradientBoostingRegressor().fit(features, past_sales)
    return np.asarray(model.predict(features))

@@ home-thermostat-optimizer
area: none
purpose: Learn when a household is usually home and preheat the house to save energy
why: no area applies, a domestic heating convenience feature, not management of critical infrastructure
labeller: author
art5: no
language: python
## requirements.txt
scikit-learn
numpy
## preheat.py
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def fit(history_hours, was_home):
    model = RandomForestClassifier(n_estimators=50)
    model.fit(np.asarray(history_hours).reshape(-1, 1), was_home)
    return model


def preheat_hours(model):
    hours = np.arange(24).reshape(-1, 1)
    return [int(h) for h, p in zip(range(24), model.predict_proba(hours)[:, 1]) if p > 0.6]

@@ lecture-notes-summarizer
area: none
purpose: Summarise recorded lecture notes so students can revise from a shorter text
why: no area applies, summarising notes does not decide admission, evaluate or monitor students
labeller: author
art5: no
language: python
## requirements.txt
transformers
torch
## summarize.py
from transformers import pipeline

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")


def summarize(notes: str, max_words: int = 120) -> str:
    out = summarizer(notes[:3000], max_length=max_words, min_length=30)
    return out[0]["summary_text"]
## cli.py
import sys

from summarize import summarize

if __name__ == "__main__":
    print(summarize(open(sys.argv[1], encoding="utf-8").read()))

@@ newsletter-spam-filter
area: none
purpose: Filter spam and promotional mail out of a team's shared inbox
why: no area applies, mail filtering does not evaluate natural persons
labeller: author
art5: no
language: python
## requirements.txt
scikit-learn
## spam.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline


def train(messages, is_spam):
    pipe = make_pipeline(TfidfVectorizer(), LogisticRegression(max_iter=300))
    return pipe.fit(messages, is_spam)


def is_spam_message(pipe, text):
    return bool(pipe.predict([text])[0])

@@ crop-leaf-disease-classifier
area: none
purpose: Classify photos of crop leaves into disease classes to advise farmers on treatment
why: no area applies, plant disease classification involves no natural persons or Annex III use
labeller: author
art5: no
language: python
## requirements.txt
torch
torchvision
pillow
## classify.py
import torch
from PIL import Image
from torchvision import models, transforms

CLASSES = ["healthy", "rust", "blight", "mildew"]
model = models.resnet18(num_classes=len(CLASSES))
model.load_state_dict(torch.load("leaf_resnet.pt"))
model.eval()
prep = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor()])


def classify(path):
    x = prep(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        return CLASSES[int(model(x).argmax())]
"""

_LANGUAGES = {"python", "javascript", "typescript", "java", "go"}


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
        assert meta["language"] in _LANGUAGES, name
        fixtures.append(
            {
                "name": name.strip(),
                "area": None if meta["area"] == "none" else int(meta["area"]),
                "purpose": meta["purpose"],
                "why": meta["why"],
                "files": contents,
                "labeller": meta["labeller"],
                "art5": meta["art5"] == "yes",
                "language": meta["language"],
            }
        )
    return fixtures


HELDOUT: list[dict] = _parse(_RAW)
