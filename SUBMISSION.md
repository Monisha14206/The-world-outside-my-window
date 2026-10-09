This is a submission for the "Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass" (https://dev.to/challenges/hacktoberfest-week1-2026-10-05)

## What I Built
The World Outside My Window is a local photo journal for time spent outdoors. After a walk, a café or a day with friends, you add photos and a few notes, and an open-weight model turns them into a first-person story, title and captions you can edit and keep. The prompt tells the model not to invent anything you didn't say, and the app also has a daily prompt that nudges you to go outside.

## Demo
Runs locally (no deployed URL). *[Add a screen recording or screenshots here before submitting.]*

## Code
*[Add your GitHub repository link here.]* Setup steps are in README.md.

## How I Built It
React + Vite frontend, Flask backend, SQLite for entries, photos on the local disk, and Ollama running `qwen2.5:3b`. Flask builds a prompt from the user's notes, feelings, places and photo captions, calls the local Ollama API, validates the JSON reply, and shows it for editing before saving. Backend tests cover CRUD, upload validation, photo cleanup and AI error handling. The model only reads text; the photos themselves are not analysed.

## Why Does Open Innovation Matter?
Because the model is open-weight, the journal can run on the user's own machine: personal photos and writing don't go to a hosted AI service, there's no API bill, and the model and prompts can be swapped or inspected. The trade-offs are real: a small model writes less polished prose, and setup takes longer. The Qwen2.5-3B licence has its own terms and isn't a standard open-source licence.

## My Agent Session (optional)
*[Add a link only if you have a real one.]*

## Prize Categories
*[Fill in only the categories you've checked you're eligible for on the challenge page.]*
