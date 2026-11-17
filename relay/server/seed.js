import "dotenv/config";
import mongoose from "mongoose";
import bcrypt from "bcryptjs";
import { fileURLToPath } from "node:url";
import { User, Client, EmailAccount } from "./models.js";
import { syncAccount } from "./data.js";
export async function seed() {
  let assistant = await User.findOne({ email: "alex@demo.com" });
  if (!assistant)
    assistant = await User.create({
      name: "Alex",
      email: "alex@demo.com",
      passwordHash: await bcrypt.hash("demo1234", 12),
      role: "assistant",
    });
  let client = await Client.findOne({
    assistantId: assistant._id,
    email: "maya@demo.com",
  });
  if (!client)
    client = await Client.create({
      name: "Maya",
      email: "maya@demo.com",
      assistantId: assistant._id,
    });
  if (!(await User.exists({ email: "maya@demo.com" })))
    await User.create({
      name: "Maya",
      email: "maya@demo.com",
      passwordHash: await bcrypt.hash("demo1234", 12),
      role: "client",
      clientId: client._id,
    });
  let account = await EmailAccount.findOne({ clientId: client._id });
  if (!account) {
    account = await EmailAccount.create({
      clientId: client._id,
      provider: "gmail",
      address: client.email,
      status: "syncing",
    });
    await syncAccount(account);
  }
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await mongoose.connect(
    process.env.MONGODB_URI || "mongodb://127.0.0.1:27017/relay",
  );
  await seed();
  await mongoose.disconnect();
  console.log("Demo seeded.");
}
