import React, { useState } from "react";
export default function ReplyComposer({ thread, action, toast }) {
  const [body, setBody] = useState(thread.draft?.body || "");
  async function generate() {
    const d = await action.mutateAsync({ path: "/ai/draft/" + thread._id });
    setBody(d.body);
    toast("Draft ready to review");
  }
  async function send() {
    if (!body.trim()) return toast("Write or draft a reply first");
    await action.mutateAsync({
      path: "/threads/" + thread._id + "/reply",
      body: { body, approved: true },
    });
    setBody("");
    toast("Reply sent · simulated delivery");
  }
  return (
    <div className="reply">
      <textarea
        aria-label="Reply"
        placeholder="Write a reply…"
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <div className="rb">
        <button
          className="btn"
          disabled={action.isPending}
          onClick={() => generate().catch(() => {})}
        >
          ✦ Draft with AI
        </button>
        <span className="mu">You review before anything is sent</span>
        <button
          className="btn p"
          disabled={action.isPending || !body.trim()}
          onClick={() => send().catch(() => {})}
        >
          Approve &amp; send
        </button>
      </div>
    </div>
  );
}
