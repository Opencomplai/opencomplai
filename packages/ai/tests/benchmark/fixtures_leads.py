"""Labelled programs for Annex III areas 3 to 8 (the "leads" benchmark set).

This set is separate from ``fixtures.py`` (the 46 training programs) and from
``heldout_fixtures.py`` (the 24 held-out programs). It exists so a later lead tier
can be measured against programs no dictionary or matcher was ever tightened
against: it is never tuned against and no program or label may be edited after a
score is seen. A miss stays a miss, a zero stays a zero.

Each program was written from the Annex III area names and sub-point titles only
(areas 3 to 8: education, employment, essential services, law enforcement,
migration, justice and democratic processes). The signal dictionary, the
matcher and the scores of the existing sets were not read while writing it.

The area label of every program is a single author's reading of the Annex III
text. It is not a legal determination and no second person has reviewed it; the
labels are data, flagged in ``LEADS_META`` for founder review.

The text lives in ``_RAW`` in a line format::

    @@ <name>
    area: <3..8 | none>
    purpose: <declared purpose>
    why: <Annex III point, or the reason no area applies>
    labeller: <author | second_pass>
    language: <python | javascript | typescript | java | go>
    kind: <positive | hard_negative>
    ## <relative path>
    <file text>

Java and Go programs carry a manifest (``pom.xml``, ``go.mod``) plus one source
file. The declared purpose is passed to the scan separately and is never written
into a program's files. Article 5 is out of scope here (the held-out set owns it).
"""

from __future__ import annotations

LEADS_META = {
    "source": (
        "Annex III areas 3 to 8 (area names and sub-point titles only); synthetic "
        "programs written for this benchmark and never tuned against"
    ),
    "confidence": "low",
    "needs_founder_review": True,
    "labelled_by": "benchmark author, single author, no second pass",
    "date": "2026-10-13",
}

_RAW = r"""
@@ exam-gaze-monitor
area: 3
purpose: Watch students through the webcam during online exams and flag suspected cheating behaviour for the invigilator
why: Annex III education 3(d), monitoring and detecting prohibited behaviour of students during tests
labeller: author
language: python
kind: positive
## requirements.txt
onnxruntime
numpy
opencv-python-headless
## monitor.py
import cv2
import numpy as np
import onnxruntime as ort

session = ort.InferenceSession("gaze_net.onnx")


def flag_frame(frame):
    face = cv2.resize(frame, (96, 96)).astype(np.float32) / 255.0
    batch = face.transpose(2, 0, 1)[None]
    off_screen, phone_visible = session.run(None, {"face": batch})[0][0]
    return off_screen > 0.8 or phone_visible > 0.6


def review(frames):
    return [i for i, f in enumerate(frames) if flag_frame(f)]

@@ admissions-applicant-ranker
area: 3
purpose: Rank applicants to the university and recommend which of them are admitted to each programme
why: Annex III education 3(a), determining access or admission of persons to educational institutions
labeller: author
language: java
kind: positive
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.admissions</groupId>
  <artifactId>applicant-ranker</artifactId>
  <version>1.4.0</version>
  <dependencies>
    <dependency>
      <groupId>com.microsoft.onnxruntime</groupId>
      <artifactId>onnxruntime</artifactId>
      <version>1.16.3</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/admissions/ApplicantRanker.java
package net.example.admissions;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import java.util.Map;

public class ApplicantRanker {
    private final OrtEnvironment env = OrtEnvironment.getEnvironment();
    private final OrtSession session;

    public ApplicantRanker(String model) throws Exception {
        this.session = env.createSession(model);
    }

    // A higher score means an earlier place on the admission list
    public float score(float[][] features) throws Exception {
        try (OnnxTensor in = OnnxTensor.createTensor(env, features)) {
            var out = session.run(Map.of("features", in));
            return ((float[][]) out.get(0).getValue())[0][0];
        }
    }
}

@@ essay-mark-assistant
area: 3
purpose: Grade student essays with a language model and set each student's mark and learning level
why: Annex III education 3(b), evaluating learning outcomes including steering a student's learning process
labeller: author
language: typescript
kind: positive
## package.json
{
  "name": "essay-mark-assistant",
  "version": "0.2.0",
  "dependencies": {
    "openai": "4.20.1",
    "typescript": "5.3.2"
  }
}
## src/grade.ts
import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.LLM_API_KEY });

export async function gradeEssay(studentId: string, essay: string) {
  const reply = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [
      { role: "system", content: "Grade this student essay from 0 to 100." },
      { role: "user", content: essay },
    ],
  });
  const mark = Number(reply.choices[0].message.content);
  return { studentId, mark, level: mark > 70 ? "advanced" : "standard" };
}

@@ candidate-screening-ranker
area: 4
purpose: Screen job applications and rank candidates so recruiters only look at the top ones
why: Annex III employment 4(a), recruitment and selection, analysing and filtering applications and evaluating candidates
labeller: author
language: python
kind: positive
## requirements.txt
scikit-learn
pandas
joblib
## rank.py
import joblib
import pandas as pd

model = joblib.load("candidate_rank.joblib")


def rank_candidates(applications: pd.DataFrame, keep: int = 20):
    features = applications[["years_experience", "skill_match", "gap_months"]]
    scored = applications.assign(score=model.predict_proba(features)[:, 1])
    return scored.sort_values("score", ascending=False).head(keep)

@@ picker-rate-scorer
area: 4
purpose: Score each warehouse worker's productivity from scan rates and flag workers for a performance warning or a termination review
why: Annex III employment 4(b), monitoring and evaluating the performance and behaviour of workers and decisions on termination
labeller: author
language: go
kind: positive
## go.mod
module example.net/pickerrate

go 1.21
## main.go
package main

import "fmt"

type Worker struct {
	ID           string
	PicksPerHr   float64
	ErrorRate    float64
	BreakMinutes int
}

// Fixed rules only: one score per worker, no model.
func score(w Worker) float64 {
	s := w.PicksPerHr / 120.0
	s -= w.ErrorRate * 5
	if w.BreakMinutes > 45 {
		s -= 0.2
	}
	return s
}

func main() {
	for _, w := range []Worker{{"w-17", 96, 0.02, 50}, {"w-21", 131, 0.01, 30}} {
		if score(w) < 0.6 {
			fmt.Println(w.ID, "performance warning")
		}
	}
}

@@ trait-based-task-allocator
area: 4
purpose: Allocate tasks and shifts to workers from a model of each worker's personal traits and past behaviour
why: Annex III employment 4(b), allocating tasks based on individual behaviour or personal traits of workers
labeller: author
language: javascript
kind: positive
## package.json
{
  "name": "trait-based-task-allocator",
  "version": "1.0.0",
  "dependencies": {
    "@tensorflow/tfjs-node": "4.15.0"
  }
}
## src/allocate.js
const tf = require("@tensorflow/tfjs-node");

let model;

async function load() {
  model = await tf.loadLayersModel("file://./models/allocator/model.json");
}

// Picks the task for a worker from traits and past behaviour
async function allocate(worker, tasks) {
  const traits = tf.tensor2d([[worker.reliability, worker.speed, worker.absences]]);
  const scores = model.predict(traits).dataSync();
  const best = scores.indexOf(Math.max(...scores));
  return { workerId: worker.id, task: tasks[best] };
}

module.exports = { load, allocate };

@@ mortgage-scorecard
area: 5
purpose: Estimate the creditworthiness of private individuals applying for a mortgage and set their credit score
why: Annex III essential_services 5(b), evaluating the creditworthiness of natural persons and establishing their credit score
labeller: author
language: python
kind: positive
## requirements.txt
scikit-learn
numpy
joblib
## scorecard.py
import joblib
import numpy as np

model = joblib.load("scorecard_gbm.joblib")


def credit_score(income, debt_ratio, years_employed, missed_payments):
    x = np.array([[income, debt_ratio, years_employed, missed_payments]])
    p_default = model.predict_proba(x)[0, 1]
    return int(850 - 550 * p_default)

@@ cover-premium-pricer
area: 5
purpose: Price life and health insurance premiums for individual customers from their medical history and lifestyle
why: Annex III essential_services 5(c), risk assessment and pricing for natural persons in life and health insurance
labeller: author
language: java
kind: positive
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.cover</groupId>
  <artifactId>premium-pricer</artifactId>
  <version>2.1.0</version>
  <dependencies>
    <dependency>
      <groupId>com.microsoft.onnxruntime</groupId>
      <artifactId>onnxruntime</artifactId>
      <version>1.16.3</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/cover/PremiumPricer.java
package net.example.cover;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import java.util.Map;

// Individual premium for a life and health policy from the applicant's risk profile
public class PremiumPricer {
    private final OrtEnvironment env = OrtEnvironment.getEnvironment();
    private final OrtSession session;

    public PremiumPricer(String path) throws Exception {
        session = env.createSession(path);
    }

    public double annualPremium(float[][] applicantRisk) throws Exception {
        try (OnnxTensor t = OnnxTensor.createTensor(env, applicantRisk)) {
            float[][] out = (float[][]) session.run(Map.of("risk", t)).get(0).getValue();
            return 240.0 + 1800.0 * out[0][0];
        }
    }
}

@@ call-queue-prioritiser
area: 5
purpose: Read incoming emergency calls and decide which ones are sent an ambulance first
why: Annex III essential_services 5(d), evaluating and classifying emergency calls and prioritising emergency first response dispatch
labeller: author
language: go
kind: positive
## go.mod
module example.net/callqueue

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

// Classifies a call transcript and returns the dispatch priority.
func priority(transcript string) (string, error) {
	client := openai.NewClient(os.Getenv("LLM_API_KEY"))
	resp, err := client.CreateChatCompletion(context.Background(), openai.ChatCompletionRequest{
		Model: openai.GPT4,
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleUser, Content: "Priority 1 to 4 for this emergency call: " + transcript},
		},
	})
	if err != nil {
		return "", err
	}
	return resp.Choices[0].Message.Content, nil
}

func main() {
	p, _ := priority("my father collapsed and is not breathing")
	fmt.Println(p)
}

@@ housing-allowance-rules
area: 5
purpose: Decide whether residents are eligible for a housing allowance and reduce or stop the payment when their income changes
why: Annex III essential_services 5(a), assessing eligibility of natural persons for public assistance benefits and granting, reducing or revoking them
labeller: author
language: python
kind: positive
## requirements.txt
pyyaml
## allowance.py
def monthly_allowance(household):
    base = 420.0
    if household["income"] > 2400:
        return 0.0
    reduction = max(0.0, household["income"] - 1200) * 0.25
    allowance = base - reduction + 60.0 * household["children"]
    return max(allowance, 0.0)


def review(household):
    amount = monthly_allowance(household)
    return {"eligible": amount > 0, "amount": round(amount, 2)}

@@ parole-reoffending-scorer
area: 6
purpose: Assess the risk that a person on parole will re-offend and give the probation officer a risk score
why: Annex III law_enforcement 6(d), assessing the risk of a natural person offending or re-offending
labeller: author
language: python
kind: positive
## requirements.txt
scikit-learn
pandas
## risk.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURES = ["age", "prior_convictions", "months_since_release", "employed"]
clf = RandomForestClassifier(n_estimators=200, random_state=0)


def fit(history: pd.DataFrame):
    clf.fit(history[FEATURES], history["reoffended"])


def risk(person: dict) -> float:
    row = pd.DataFrame([person])[FEATURES]
    return float(clf.predict_proba(row)[0, 1])

@@ witness-statement-reliability
area: 6
purpose: Evaluate the reliability of witness statements and digital evidence collected in a criminal investigation
why: Annex III law_enforcement 6(c), evaluating the reliability of evidence in the investigation or prosecution of criminal offences
labeller: author
language: typescript
kind: positive
## package.json
{
  "name": "witness-statement-reliability",
  "version": "0.5.0",
  "dependencies": {
    "@google/generative-ai": "0.2.1",
    "typescript": "5.3.2"
  }
}
## src/reliability.ts
import { GoogleGenerativeAI } from "@google/generative-ai";

const genai = new GoogleGenerativeAI(process.env.LLM_API_KEY ?? "");
const model = genai.getGenerativeModel({ model: "gemini-1.5-flash" });

// Evidence reliability score for an investigation file
export async function reliability(statement: string): Promise<number> {
  const result = await model.generateContent(
    `Rate from 0 to 100 how reliable this evidence is: ${statement}`
  );
  return Number(result.response.text());
}

@@ repeat-victim-risk-rules
area: 6
purpose: Assess the risk that a person becomes the victim of a repeat offence and set a protection priority for the police
why: Annex III law_enforcement 6(a), assessing the risk of a natural person becoming the victim of criminal offences
labeller: author
language: java
kind: positive
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.protect</groupId>
  <artifactId>repeat-victim-risk</artifactId>
  <version>1.0.2</version>
</project>
## src/main/java/net/example/protect/VictimRisk.java
package net.example.protect;

import java.util.Map;

// Rule table, no model: one weight per reported factor
public class VictimRisk {
    private static final Map<String, Integer> WEIGHTS = Map.of(
        "prior_incidents", 30,
        "separated_recently", 20,
        "threats_reported", 35,
        "weapon_access", 15);

    public int score(Map<String, Boolean> factors) {
        int total = 0;
        for (var e : factors.entrySet()) {
            if (e.getValue()) {
                total += WEIGHTS.getOrDefault(e.getKey(), 0);
            }
        }
        return total;
    }
}

@@ visa-application-risk-score
area: 7
purpose: Score each visa and residence permit application for the risk of irregular migration and route high scores to a caseworker
why: Annex III migration 7(b), assessing the risk, including irregular migration risk, posed by a person who applies to enter or reside
labeller: author
language: python
kind: positive
## requirements.txt
onnxruntime
numpy
## routing.py
import numpy as np
import onnxruntime as ort

sess = ort.InferenceSession("visa_risk.onnx")


def application_risk(age, prior_refusals, travel_days, sponsor_known):
    x = np.array([[age, prior_refusals, travel_days, sponsor_known]], dtype=np.float32)
    return float(sess.run(None, {"input": x})[0][0][0])


def route(app):
    return "caseworker" if application_risk(**app) > 0.7 else "standard"

@@ checkpoint-face-matcher
area: 7
purpose: Identify persons at a border checkpoint by matching a face image against the entry watchlist
why: Annex III migration 7(d), detecting, recognising or identifying natural persons in the context of border control
labeller: author
language: go
kind: positive
## go.mod
module example.net/checkpointface

go 1.21

require github.com/yalue/onnxruntime_go v1.9.0
## main.go
package main

import (
	"fmt"

	ort "github.com/yalue/onnxruntime_go"
)

// Embeds a face image so it can be compared with the watchlist.
func main() {
	if err := ort.InitializeEnvironment(); err != nil {
		panic(err)
	}
	defer ort.DestroyEnvironment()
	input, _ := ort.NewTensor(ort.NewShape(1, 3, 112, 112), make([]float32, 3*112*112))
	output, _ := ort.NewEmptyTensor[float32](ort.NewShape(1, 512))
	session, err := ort.NewAdvancedSession("face_embed.onnx",
		[]string{"image"}, []string{"embedding"},
		[]ort.ArbitraryTensor{input}, []ort.ArbitraryTensor{output}, nil)
	if err != nil {
		panic(err)
	}
	_ = session.Run()
	fmt.Println(len(output.GetData()))
}

@@ asylum-evidence-checker
area: 7
purpose: Assist asylum officers by assessing whether the evidence in each asylum application is reliable and drafting a recommendation
why: Annex III migration 7(c), examining applications for asylum and assessing the reliability of evidence
labeller: author
language: javascript
kind: positive
## package.json
{
  "name": "asylum-evidence-checker",
  "version": "0.9.0",
  "dependencies": {
    "openai": "4.20.1"
  }
}
## src/assess.js
const OpenAI = require("openai");

const client = new OpenAI({ apiKey: process.env.LLM_API_KEY });

async function assessApplication(application) {
  const reply = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "Assess how reliable the evidence is and recommend grant or refuse." },
      { role: "user", content: JSON.stringify(application) },
    ],
  });
  return reply.choices[0].message.content;
}

module.exports = { assessApplication };

@@ judgment-drafting-assistant
area: 8
purpose: Help judges research the facts and the law of a case and apply the law to the facts in a draft ruling
why: Annex III justice_democracy 8(a), assisting a judicial authority in researching and interpreting facts and law and applying the law to facts
labeller: author
language: python
kind: positive
## requirements.txt
openai
## draft.py
import os

from openai import OpenAI

client = OpenAI(api_key=os.environ["LLM_API_KEY"])


def draft_ruling(facts: str, statutes: list[str]) -> str:
    prompt = "Apply these statutes to the facts and draft a ruling.\nFacts: " + facts
    prompt += "\nStatutes: " + "; ".join(statutes)
    reply = client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
    )
    return reply.choices[0].message.content

@@ voter-persuasion-targeting
area: 8
purpose: Predict which voters can be persuaded and choose the message that most changes how they vote in the referendum
why: Annex III justice_democracy 8(b), influencing the outcome of an election or referendum or the voting behaviour of natural persons
labeller: author
language: python
kind: positive
## requirements.txt
scikit-learn
pandas
## targeting.py
import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES = ["age", "turnout_history", "issue_score", "region_code"]
uplift = LogisticRegression(max_iter=500)


def fit(voters: pd.DataFrame):
    uplift.fit(voters[FEATURES], voters["changed_vote_after_contact"])


def targets(voters: pd.DataFrame, top: int = 5000):
    voters = voters.assign(p=uplift.predict_proba(voters[FEATURES])[:, 1])
    return voters.nlargest(top, "p")["voter_id"].tolist()

@@ mediation-settlement-recommender
area: 8
purpose: Recommend a settlement outcome for each dispute submitted to an alternative dispute resolution body
why: Annex III justice_democracy 8(a), a system used in a similar way in alternative dispute resolution to apply the law to the facts
labeller: author
language: java
kind: positive
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.mediation</groupId>
  <artifactId>settlement-recommender</artifactId>
  <version>0.7.0</version>
  <dependencies>
    <dependency>
      <groupId>com.theokanning.openai-gpt3-java</groupId>
      <artifactId>service</artifactId>
      <version>0.18.2</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/mediation/SettlementRecommender.java
package net.example.mediation;

import com.theokanning.openai.completion.chat.ChatCompletionRequest;
import com.theokanning.openai.completion.chat.ChatMessage;
import com.theokanning.openai.service.OpenAiService;
import java.util.List;

public class SettlementRecommender {
    private final OpenAiService service = new OpenAiService(System.getenv("LLM_API_KEY"));

    public String recommend(String dispute) {
        var request = ChatCompletionRequest.builder()
            .model("gpt-4o")
            .messages(List.of(new ChatMessage("user", "Recommend a settlement for: " + dispute)))
            .build();
        return service.createChatCompletion(request).getChoices().get(0).getMessage().getContent();
    }
}

@@ practice-quiz-generator
area: none
purpose: Generate practice quiz questions on a topic that students can use to revise on their own
why: no area applies, it writes revision content and does not admit, grade or monitor any student
labeller: author
language: python
kind: hard_negative
## requirements.txt
openai
## quiz.py
import os

from openai import OpenAI

client = OpenAI(api_key=os.environ["LLM_API_KEY"])


def make_quiz(topic: str, count: int = 10) -> str:
    reply = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Write {count} multiple choice questions about {topic}"}
        ],
    )
    return reply.choices[0].message.content

@@ job-board-search-index
area: none
purpose: Index public job postings so that visitors can search them by keyword and location
why: no area applies, it searches postings and does not screen, rank or evaluate any candidate
labeller: author
language: typescript
kind: hard_negative
## package.json
{
  "name": "job-board-search-index",
  "version": "1.2.0",
  "dependencies": {
    "minisearch": "6.3.0",
    "typescript": "5.3.2"
  }
}
## src/index.ts
import MiniSearch from "minisearch";

type Posting = { id: string; title: string; company: string; location: string };

export const index = new MiniSearch<Posting>({
  fields: ["title", "company", "location"],
  storeFields: ["title", "company", "location"],
});

export function addPostings(postings: Posting[]) {
  index.addAll(postings);
}

export function search(query: string, location?: string) {
  return index.search(query, { filter: (r) => !location || r.location === location });
}

@@ card-transaction-fraud-alert
area: none
purpose: Raise an alert when a card transaction looks like fraud so the bank can block the card
why: no area applies, Annex III 5(b) excludes systems used to detect financial fraud
labeller: author
language: python
kind: hard_negative
## requirements.txt
scikit-learn
numpy
## alert.py
import numpy as np
from sklearn.ensemble import IsolationForest

detector = IsolationForest(contamination=0.002, random_state=0)


def train(history: np.ndarray):
    detector.fit(history)


def is_suspicious(amount: float, hour: int, distance_km: float) -> bool:
    return detector.predict(np.array([[amount, hour, distance_km]]))[0] == -1

@@ closed-file-keyword-search
area: none
purpose: Full-text search over closed police case files so officers can find a file by case number or keyword
why: no area applies, plain retrieval of files that evaluates no person and no evidence
labeller: author
language: java
kind: hard_negative
## pom.xml
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>net.example.casefiles</groupId>
  <artifactId>closed-file-search</artifactId>
  <version>1.1.0</version>
  <dependencies>
    <dependency>
      <groupId>org.apache.lucene</groupId>
      <artifactId>lucene-core</artifactId>
      <version>9.9.1</version>
    </dependency>
  </dependencies>
</project>
## src/main/java/net/example/casefiles/FileSearch.java
package net.example.casefiles;

import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.store.Directory;

public class FileSearch {
    private final IndexSearcher searcher;

    public FileSearch(Directory dir) throws Exception {
        this.searcher = new IndexSearcher(DirectoryReader.open(dir));
    }

    // Plain keyword retrieval of closed files by number or term
    public ScoreDoc[] find(Query query) throws Exception {
        return searcher.search(query, 25).scoreDocs;
    }
}

@@ office-form-translator
area: none
purpose: Translate forms and letters received by the immigration office into the officers' working language
why: no area applies, it translates text and does not examine an application or assess any person
labeller: author
language: python
kind: hard_negative
## requirements.txt
openai
## translate.py
import os

from openai import OpenAI

client = OpenAI(api_key=os.environ["LLM_API_KEY"])


def translate(text: str, target: str = "English") -> str:
    reply = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Translate the user text into {target}. Output only the translation."},
            {"role": "user", "content": text},
        ],
    )
    return reply.choices[0].message.content

@@ weekly-rota-planner
area: none
purpose: Build a weekly staff rota that covers every shift from the availability the employees entered
why: no area applies, a rota planner that uses stated availability only and sets no evaluation of any person
labeller: author
language: go
kind: hard_negative
## go.mod
module example.net/rotaplanner

go 1.21
## main.go
package main

import "fmt"

type Slot struct {
	Day   string
	Hours int
}

func plan(available map[string][]string, slots []Slot) map[string]string {
	rota := map[string]string{}
	for _, s := range slots {
		for name, days := range available {
			for _, d := range days {
				if d == s.Day && rota[s.Day] == "" {
					rota[s.Day] = name
				}
			}
		}
	}
	return rota
}

func main() {
	fmt.Println(plan(map[string][]string{"ana": {"mon"}, "ben": {"wed"}}, []Slot{{"mon", 8}, {"wed", 8}}))
}

@@ fleet-route-optimiser
area: none
purpose: Compute the shortest driving routes for the ambulance fleet between the depot and the hospitals
why: no area applies, vehicle routing does not classify calls or prioritise any patient
labeller: author
language: python
kind: hard_negative
## requirements.txt
ortools
## routes.py
from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def solve(distance_matrix, vehicles, depot=0):
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)

    def cost(a, b):
        return distance_matrix[manager.IndexToNode(a)][manager.IndexToNode(b)]

    handle = routing.RegisterTransitCallback(cost)
    routing.SetArcCostEvaluatorOfAllVehicles(handle)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    return routing.SolveWithParameters(params)

@@ school-timetable-builder
area: none
purpose: Generate the school timetable that assigns classes to rooms and teachers to periods without clashes
why: no area applies, room and period scheduling does not decide admission or evaluate any student
labeller: author
language: javascript
kind: hard_negative
## package.json
{
  "name": "school-timetable-builder",
  "version": "2.0.0",
  "dependencies": {}
}
## src/build.js
function build(classes, rooms, periods) {
  const table = {};
  for (const cls of classes) {
    for (const period of periods) {
      const room = rooms.find((r) => !table[`${period}:${r}`]);
      if (room) {
        table[`${period}:${room}`] = cls;
        break;
      }
    }
  }
  return table;
}

module.exports = { build };

@@ campaign-volunteer-mailer
area: none
purpose: Schedule and send volunteer rota reminders and event invitations to the people who signed up for the campaign
why: no area applies, Annex III 8(b) excludes tools used for the administrative and logistical organisation of campaigns
labeller: author
language: typescript
kind: hard_negative
## package.json
{
  "name": "campaign-volunteer-mailer",
  "version": "1.3.0",
  "dependencies": {
    "nodemailer": "6.9.7",
    "typescript": "5.3.2"
  }
}
## src/remind.ts
import nodemailer from "nodemailer";

const transport = nodemailer.createTransport({ host: process.env.SMTP_HOST });

export async function sendReminder(to: string, shift: string) {
  await transport.sendMail({
    from: "volunteers@campaign.example.org",
    to,
    subject: "Your volunteer shift",
    text: `You are on the rota for ${shift}. Thank you for helping.`,
  });
}
"""

_LANGUAGES = {"python", "javascript", "typescript", "java", "go"}
_KINDS = {"positive", "hard_negative"}


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
        assert meta["kind"] in _KINDS, name
        fixtures.append(
            {
                "name": name.strip(),
                "area": None if meta["area"] == "none" else int(meta["area"]),
                "purpose": meta["purpose"],
                "why": meta["why"],
                "files": contents,
                "labeller": meta["labeller"],
                "language": meta["language"],
                "kind": meta["kind"],
            }
        )
    return fixtures


LEADS: list[dict] = _parse(_RAW)
