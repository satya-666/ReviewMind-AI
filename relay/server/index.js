import "dotenv/config";
import mongoose from "mongoose";
import { createApp } from "./app.js";
await mongoose.connect(
  process.env.MONGODB_URI || "mongodb://127.0.0.1:27017/relay",
);
const app = createApp();
app.listen(process.env.PORT || 4000, "0.0.0.0", () =>
  console.log("Relay API ready"),
);
