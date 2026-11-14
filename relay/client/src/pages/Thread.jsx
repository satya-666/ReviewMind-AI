import React from "react";
import { useApi, useAction } from "../hooks/useApi";
import {
  Skeleton,
  ErrorState,
  OwnerSwitcher,
  AiSummary,
} from "../components/Common";
import ReplyComposer from "../components/ReplyComposer";
export default function Thread({ id, close, toast }) {
  const query = useApi("/threads/" + id),
    action = useAction(toast);
  if (query.isPending) return <Skeleton />;
  if (query.isError) return <ErrorState query={query} />;
  const t = query.data;
  async function patch(body) {
    await action.mutateAsync({ path: "/threads/" + id, method: "PATCH", body });
    toast("Conversation updated");
    if (body.archived || body.done || body.unread) close();
  }
  return (
    <div className="det">
      <button className="back" onClick={close}>
        ‹ Back
      </button>
      <div className="mu">{t.participants.join(" · ")}</div>
      <h2>{t.subject}</h2>
      <OwnerSwitcher
        owner={t.classification.owner}
        disabled={action.isPending}
        onChange={(owner) =>
          patch({ classification: { owner } }).catch(() => {})
        }
      />
      <div className="acts">
        {[
          [
            t.important ? "★ Important" : "☆ Mark important",
            { important: !t.important },
          ],
          ["Mark unread", { unread: true }],
          [t.archived ? "Unarchive" : "Archive", { archived: !t.archived }],
          ["Mark done", { done: true }],
        ].map(([label, body]) => (
          <button
            className="btn"
            key={label}
            disabled={action.isPending}
            onClick={() => patch(body).catch(() => {})}
          >
            {label}
          </button>
        ))}
      </div>
      <AiSummary thread={t} />
      {t.messages.map((m) => (
        <div className="msg" key={m._id}>
          <div className="mh">
            <b>{m.from}</b>
            <span className="mu">{new Date(m.sentAt).toLocaleString()}</span>
          </div>
          <p>{m.body}</p>
        </div>
      ))}
      <ReplyComposer key={id} thread={t} action={action} toast={toast} />
      <div className="ai">
        <h4>Activity</h4>
        {t.activity.map((a) => (
          <p className="mu" key={a._id}>
            {a.actor} · {a.action} · {new Date(a.at).toLocaleString()}
          </p>
        ))}
      </div>
    </div>
  );
}
