import { VertexAI } from "@google-cloud/vertexai";

// Initialize Vertex AI with Google Cloud credentials
const vertexAI = new VertexAI({
  project: "friendlyfoes",  // Ensure this matches your active GCP project
  location: "us-central1",  // Set the correct region
});

// Get a model instance
const model = vertexAI.getGenerativeModel({ model: "gemini-pro" });

function isGameSpecificQuestion(question) {
  const gameKeywords = [
    "who is playing",
    "who won",
    "score",
    "result",
    "teams",
    "players",
    "game",
  ];
  return gameKeywords.some((keyword) => question.toLowerCase().includes(keyword));
}

async function fetchAndProcessGameData(gamePk) {
  const gameData = await fetchHistoricalGameData(gamePk);
  if (!gameData) {
    return "Sorry, I couldn't fetch the game data.";
  }

  const gameInfo = extractHistoricalGameInfo(gameData);
  return gameInfo;
}

async function generateGameSpecificResponse(question, gameInfo) {
  const prompt = `
    You are Rival, a baseball chat assistant. Answer the user's question about the game.
    User's question: "${question}"
    Game information:
    - Teams: ${gameInfo.teams.home.name} (Home) vs ${gameInfo.teams.away.name} (Away)
    - Final Score: Home ${gameInfo.finalScore.home} - Away ${gameInfo.finalScore.away}
    - Winning Team: ${gameInfo.winningTeam}
    - Key Events: ${gameInfo.keyEvents.join(", ")}
    Write a short, engaging response in under 50 words.
  `;

  const response = await callGenerativeAIanswer(prompt);
  return response;
}
/**
 * Calls Gemini AI with a user question + optional MLB stats.
 * @param {string} question - The user’s question or prompt.
 * @returns {Promise<string>} The AI-generated response text.
 */
export async function callGenerativeAIanswer(question, gamePk) {
  console.log("Inside callGenerativeAIanswer with question:", question);

  // Check if the question is about the game
  if (isGameSpecificQuestion(question)) {
    const gameInfo = await fetchAndProcessGameData(gamePk);
    if (typeof gameInfo === "string") {
      return gameInfo; // Return error message if fetching game data failed
    }
    return generateGameSpecificResponse(question, gameInfo);
  }

  // If not a game-specific question, proceed with the original logic
  const playerName = detectPlayerName(question);
  let stats = "";
  if (playerName) {
    stats = await fetchPlayerStats(playerName);
  }

  // Construct prompt
  const systemPrompt = `
    You are Rival, a helpful baseball chat assistant. 
    The user asked: "${question}"
    Additional info: ${stats}
    Based on this, answer in a friendly style.
    Answer in at most 50 words.
    Do not ask if the user needs further assistance.
  `;

  try {
    console.log("Attempting to call Gemini with prompt:", systemPrompt);

    const result = await model.generateContent(systemPrompt);
    const response = await result.response;
    console.log(JSON.stringify(response, null, 2)); // Added for debugging
    const answer = response.candidates[0].content;

    console.log("Sending back answer:", answer);
    return answer;
  } catch (err) {
    console.error("Error calling Gemini:", err.message, err);
    return "Error calling Gemini.";
  }
}

/**
 * Helper: Basic approach to parse a known set of player names.
 * @param {string} text - The user's input.
 * @returns {string|null} The matched player name or null if not found.
 */
function detectPlayerName(text) {
  const knownPlayers = ["ohtani", "trout", "kershaw", "de la cruz"];
  const words = text.toLowerCase().split(/\s+/);
  const found = words.find((w) => knownPlayers.includes(w));
  return found || null;
}

/**
 * Helper: If a recognized player, fetch stats from MLB Stats API.
 * @param {string} playerName
 * @returns {Promise<string>} A short string summarizing the player's stats or an error.
 */
async function fetchPlayerStats(playerName) {
  let playerId = null;
  if (playerName === "ohtani") playerId = 660271;
  else if (playerName === "trout") playerId = 545361;
  else if (playerName === "kershaw") playerId = 477132;

  if (!playerId) return "No known stats for that player.";

  try {
    const url = `https://statsapi.mlb.com/api/v1/people/${playerId}/stats?stats=season&season=2023`;
    const response = await fetch(url);
    const data = await response.json();
    if (data.stats?.[0]?.splits?.[0]?.stat) {
      const s = data.stats[0].splits[0].stat;
      return `Stats: HR=${s.homeRuns}, BA=${s.avg}, ERA=${s.era || "N/A"}, ...`;
    } else {
      return "No stats found in the feed.";
    }
  } catch (err) {
    console.error(err);
    return "Error fetching stats from MLB API.";
  }
}

/**
 * Fetches historical game data from the MLB API.
 * @param {string} gamePk - The game ID.
 * @returns {Promise<object|null>} The game data or null if an error occurs.
 */
export async function fetchHistoricalGameData(gamePk) {
  const url = `https://statsapi.mlb.com/api/v1/game/${gamePk}/feed/live`;
  try {
    const response = await fetch(url);
    const data = await response.json();

    // Check for errors in the response
    if (data.error || data.message) {
      console.error("API returned an error:", data.error || data.message);
      return null;
    }
    console.log("Full API response:", data); // Log the entire response

    // Log only the most relevant parts of the data
    console.log("Fetched game data (subset):", {
      gameData: {
        gamePk: data.gamePk,
        status: data.gameData?.status?.detailedState,
        teams: { 
          home: data.gameData?.teams?.home?.name,
          away: data.gameData?.teams?.away?.name,
        },
      },
      liveData: {
        boxscore: {
          home: {
            runs: data.liveData?.boxscore?.teams?.home?.teamStats?.batting?.runs,
          },
          away: {
            runs: data.liveData?.boxscore?.teams?.away?.teamStats?.batting?.runs,
          },
        },
        plays: data.liveData?.plays?.allPlays?.slice(0, 3), // Log only the first 3 plays
      },
    });   
  return data;
  } catch (error) {
    console.error("Error fetching historical game data:", error);
    return null;
  }
}

/**
 * Extracts relevant information from historical game data.
 * @param {object} gameData - The game data from the MLB API.
 * @returns {object} Extracted game information.
 */
export function extractHistoricalGameInfo(gameData) {
  if (!gameData || !gameData.liveData || !gameData.gameData) {
    console.error("Invalid game data provided.");
    return null;
  }

  try {
    const { liveData, gameData: metaData } = gameData;
    const { boxscore, plays } = liveData;
    const { teams } = boxscore;
    
    if (!teams || !teams.home || !teams.away) {
      console.error("Team data is missing.");
      return null;
    }

    const homeTeam = teams.home;
    const awayTeam = teams.away;

    // Extract final score
    const homeScore = homeTeam.teamStats?.batting?.runs ?? 0;
    const awayScore = awayTeam.teamStats?.batting?.runs ?? 0;

    // Determine winner
    let winningTeam = "Tie"; // Default case in case of tie
    if (homeScore > awayScore) {
      winningTeam = homeTeam.team?.name ?? "Home Team";
    } else if (awayScore > homeScore) {
      winningTeam = awayTeam.team?.name ?? "Away Team";
    }

    // Game Status
    const gameStatus = metaData.status?.detailedState ?? "Unknown";
    // Extract key events (descriptions of plays)
    const keyEvents = plays?.allPlays?.map((play) => play.result.description) ?? [];

    return {
      finalScore: {
        home: homeScore,
        away: awayScore,
      },
      winningTeam,
      summary: gameStatus,
      keyEvents,
    };
  } catch (error) {
    console.error("Error extracting game info:", error);
    return null;
  }
}


/**
 * Generates an AI-driven message about a historical game.
 * @param {object} gameInfo - Extracted game information.
 * @returns {Promise<string>} The AI-generated message.
 */
export async function generateHistoricalGameMessage(gameInfo) {
  const prompt = `
    You are Rival, a baseball chat assistant. Provide a short summary and interesting insights about a past game.
    Final Score: Home ${gameInfo.finalScore.home} - Away ${gameInfo.finalScore.away}
    Winning Team: ${gameInfo.winningTeam}
    Key Events:  ${gameInfo.keyEvents.join(", ")}
    Write a short, engaging summary in under 50 words.
  `;

  const message = await callGenerativeAIanswer(prompt);
  return message;
}