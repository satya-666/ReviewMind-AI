import { samples } from "../sample.js";
export class EmailProvider {
  async listThreads() {
    throw new Error("Not implemented");
  }
  async getThread() {
    throw new Error("Not implemented");
  }
  async sendReply() {
    throw new Error("Not implemented");
  }
}
const additional = [
  [
    "Aisha Patel",
    "aisha@northwind.co",
    "Board pack: approval before circulation",
    "The board pack is ready. Maya, can you approve the budget notes before we circulate on 2026-11-20?",
  ],
  [
    "Ben Walsh",
    "ben@fieldwork.co",
    "Visitor names for Tuesday",
    "Could you send the visitor names and dietary requirements for Tuesday’s office visit?",
  ],
  [
    "Notion",
    "receipts@notion.so",
    "Receipt for your team plan",
    "Automated receipt: your team plan payment is complete. No reply is needed.",
  ],
  [
    "Clara Wu",
    "clara@harbor.events",
    "Summit rehearsal scheduling",
    "Can we schedule a 20-minute rehearsal call on 2026-11-23? Please suggest a time.",
  ],
  [
    "Eli Grant",
    "eli@cedar.vc",
    "A small dinner with founders?",
    "Not sure if this is the right group for Maya. Would she like a personal introduction?",
  ],
  [
    "Farah Khan",
    "farah@northwind.co",
    "Press quote: final approval",
    "Maya, we need your approval of the quote before the announcement goes live.",
  ],
  [
    "GitHub",
    "notifications@github.com",
    "Your weekly activity digest",
    "Automated notification: here is this week’s repository activity.",
  ],
  [
    "Grace Bell",
    "grace@atlas.travel",
    "Airport transfer details",
    "Please send the flight number so we can arrange the airport transfer.",
  ],
  [
    "Hugo Silva",
    "hugo@solstice.io",
    "Vendor onboarding paperwork",
    "Could your assistant return the vendor contact form and billing address?",
  ],
  [
    "Iris Chen",
    "iris@northwind.co",
    "Acquisition terms: confidential",
    "This is a sensitive negotiation. Maya, I need your personal decision on the counteroffer.",
  ],
  [
    "Julian Reed",
    "julian@studio.one",
    "Workshop agenda confirmed",
    "Confirmed: we have everything we need. Thank you, that resolves our questions.",
  ],
  [
    "Lara Moss",
    "lara@commonroom.org",
    "Community newsletter: November",
    "Newsletter: this month’s community stories and events.",
  ],
  [
    "Nikhil Rao",
    "nikhil@pine.design",
    "Could we reschedule the kickoff?",
    "Please move the kickoff meeting to 2026-11-25 and send an updated invitation.",
  ],
  [
    "Olivia Hart",
    "olivia@meridian.co",
    "Reference request for an old colleague",
    "Maybe Maya would prefer to answer personally. Could you check whether she wants to provide a reference?",
  ],
  [
    "Sam Rivera",
    "sam@folio.press",
    "Biography and headshot request",
    "Please send an updated speaker biography and headshot for the conference programme.",
  ],
  [
    "Tessa Young",
    "tessa@northwind.co",
    "Charitable pledge: your decision",
    "Maya, this pledge needs your personal approval before we make a financial commitment.",
  ],
].map(([f, e, s, body], i) => ({
  id: i + 10,
  f,
  e,
  s,
  u: i < 4,
  im: /approval|confidential/.test(s),
  th: [
    [
      "Alex (for Maya)",
      "Earlier",
      `Thanks for getting in touch about ${s.toLowerCase()}. Please send the details.`,
    ],
    [f, "Today", body],
  ],
}));
export class MockEmailProvider extends EmailProvider {
  async listThreads() {
    return [...samples, ...additional].map((sample) => ({
      ...sample,
      th:
        sample.th.length > 1
          ? sample.th
          : [
              [
                "Alex (for Maya)",
                "Earlier",
                `Following up on ${sample.s.toLowerCase()}.`,
              ],
              ...sample.th,
            ],
    }));
  }
  async getThread(id) {
    return (await this.listThreads()).find((t) => t.id === id);
  }
  async sendReply() {
    return { simulated: true };
  }
}
