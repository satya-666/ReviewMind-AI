export function classifyMock({ thread, messages, client }) {
  const last = messages.at(-1),
    text = (
      thread.subject +
      " " +
      (last?.from || "") +
      " " +
      (last?.body || "")
    ).toLowerCase();
  let owner = "assistant",
    confidence = 91,
    reason = "You can handle this routine administrative follow-up.";
  if (
    /newsletter|receipt|stripe.*invoice|already paid|automated|markets rally|confirmed|resolved|thank you, that resolves/.test(
      text,
    )
  ) {
    owner = "none";
    confidence = 99;
    reason = "This is automated or resolved; no response is expected.";
  } else if (/intro to|want me to connect|maybe|not sure/.test(text)) {
    owner = "review";
    confidence = 48;
    reason = "You should review this ambiguous personal networking decision.";
  } else if (
    /sign.off|approval|approve|allocation|negotiat|between us|personal decision|sensitive|your decision/.test(
      text,
    )
  ) {
    owner = "client";
    confidence = 96;
    reason = `${client.name} needs to make this personal approval or sensitive decision.`;
  }
  const waiting = last?.direction === "outbound";
  if (waiting) {
    owner = "none";
    confidence = 95;
    reason = "You have already replied; wait for an inbound response.";
  }
  const dates = [...text.matchAll(/\b(?:20\d\d-\d{2}-\d{2})\b/g)].map((m) => ({
    label: "Mentioned date",
    date: m[0],
  }));
  return {
    owner,
    confidence,
    reason,
    summary: (last?.body || thread.subject)
      .split(/(?<=[.!?])\s+/)
      .slice(0, 2)
      .join(" "),
    dates,
    isMeeting: /call|meeting|reschedul|dinner|summit/.test(text),
    waiting,
  };
}
export function askMock(question, threads) {
  const q = question.toLowerCase();
  let found;
  if (/why/.test(q)) {
    found = threads.filter(
      (t) =>
        t.owner === "client" &&
        (q.includes(t.subject.toLowerCase()) ||
          q.includes(t.sender.toLowerCase())),
    );
    if (!found.length) found = threads.filter((t) => t.owner === "client");
  } else if (/wait/.test(q)) found = threads.filter((t) => t.waiting);
  else if (/review|unsure/.test(q))
    found = threads.filter((t) => t.owner === "review");
  else if (/client|attention/.test(q))
    found = threads.filter((t) => t.owner === "client");
  else if (/assistant|reply/.test(q))
    found = threads.filter((t) => t.owner === "assistant");
  else
    found = threads.filter((t) =>
      (t.subject + " " + t.summary + " " + t.sender).toLowerCase().includes(q),
    );
  return {
    answer: found.length
      ? found
          .map((t) => `${t.subject}: ${/why/.test(q) ? t.reason : t.summary}`)
          .join("\n")
      : "No matching conversations. Try asking what needs the client’s attention, what you are waiting on, or which emails need review.",
    threadIds: found.map((t) => t.id),
  };
}
export function draftMock({ client, messages }) {
  return `Hi ${(messages.find((m) => m.direction === "inbound")?.from || "there").split(" ")[0]},\n\nThanks for your message. I’m checking this with ${client.name} and will follow up shortly.\n\nBest,\nAlex (for ${client.name})`;
}
