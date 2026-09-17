import { createOpenAI } from "@ai-sdk/openai";
import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";

const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });

export async function viaVercelOpenAI(prompt: string) {
  return generateText({ model: openai("gpt-4-0613"), prompt });
}

export async function viaVercelAnthropic(prompt: string) {
  return generateText({ model: anthropic("claude-3-opus-20240229"), prompt });
}
