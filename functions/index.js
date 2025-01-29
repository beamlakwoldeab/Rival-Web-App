import functions from "firebase-functions";
import express from "express";
import cors from "cors"; // Import CORS
import { callGenerativeAIanswer, fetchHistoricalGameData, extractHistoricalGameInfo, generateHistoricalGameMessage } from "./aiLogic.js";

const app = express(); 

// Enable CORS for all routes
app.use(cors({ origin: 'https://rival2.web.app' })); // Allow requests from your frontend
app.use(express.json()); // Parse JSON request bodies

// Handle preflight requests for all routes
app.options("*", cors()); // Allow preflight requests for all routes

// The route for AI calls
app.post("/ai", async (req, res) => {
  try {
    const question = req.body.question || "";
    const gamePk = req.body.gamePk; // Get gamePk from the request body
    const answer = await callGenerativeAIanswer(question, gamePk); // Pass gamePk
    return res.json({ answer });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to process AI request" });
  }
});

// Route for historical game data
app.post("/historical-game", async (req, res) => {
  try {
    const gamePk = req.body.gamePk; // Get gamePk from the request body
    if (!gamePk) {
      return res.status(400).json({ error: "gamePk is required" });
    }

    // Fetch and process historical game data
    const gameData = await fetchHistoricalGameData(gamePk);
    if (!gameData) {
      return res.status(500).json({ error: "Failed to fetch game data" });
    }

    const gameInfo = extractHistoricalGameInfo(gameData);
    const message = await generateHistoricalGameMessage(gameInfo);

    return res.json({ message });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to process historical game data" });
  }
});

// Export the Cloud Function
export const api = functions.https.onRequest(app);