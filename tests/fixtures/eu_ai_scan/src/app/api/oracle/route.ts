import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return Response.json({ error: "Oracle is not configured." }, { status: 503 });
  }

  const geminiRes = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: "hello" }] }],
        generationConfig: { maxOutputTokens: 512, temperature: 0.1 },
      }),
    },
  );

  const data = await geminiRes.json();
  return Response.json({ answer: data.candidates?.[0]?.content?.parts?.[0]?.text ?? "" });
}
