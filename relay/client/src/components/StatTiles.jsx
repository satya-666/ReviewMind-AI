import React from "react";
export default function StatTiles({ stats, go, setUnread }) {
  return (
    <div className="stats">
      {[
        ["Unread", stats?.unread, "all"],
        ["Assistant to reply", stats?.assistant, "assistant"],
        ["Client to reply", stats?.client, "client"],
        ["Needs review", stats?.review, "review"],
      ].map(([label, value, key]) => (
        <button
          className="st"
          key={label}
          onClick={() => {
            go(key);
            setUnread(label === "Unread");
          }}
        >
          <b>{value || 0}</b>
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
