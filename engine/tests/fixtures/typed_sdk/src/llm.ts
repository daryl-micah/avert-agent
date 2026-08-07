import OpenAI from "openai";

const client = new OpenAI();

async function callLiteral() {
  return client.chat.completions.create({ model: "gpt-4-0613", messages: [] });
}

async function callDynamic(modelName: string) {
  return client.chat.completions.create({ model: modelName, messages: [] });
}
