# Golden Cases

These cases are used to check behavior and do not require word-for-word matching.

## 1. Personal Tool

Input:

> I want to make a batch file renaming software and may open-source it in the future.

Expectations:

- Prioritize confirming real pain points and whether the user themselves can accept CLI;
- "May open-source in the future" does not automatically trigger accounts, telemetry, or auto-updates;
- Check whether existing tools or scripts are already sufficient;
- Do not enter GUI framework or language selection.

## 2. Existing Mature Open-Source Project

Input:

> I want to build a video subtitle tool from scratch.

Expectations:

- Identify the truly inadequate parts of the existing subtitle workflow;
- Proactively search for existing open-source and commercial solutions;
- Compare scripts, plugins, forks, combinations, and building from scratch;
- Do not recommend a complete rewrite without sufficient justification.

## 3. Conflicting Goals

Input:

> Only for my own use, but it must allow people who know nothing about computers to install and use it directly.

Expectations:

- Point out that the two goals bring different scopes;
- Explain the complexity differences between personal use and public release;
- Only ask the user to decide who the first phase serves;
- Do not silently merge the two goals.

## 4. Commercial Service

Input:

> I want to build an online document processing service for enterprise paid use.

Expectations:

- Further confirm data responsibility, failure consequences, user scale, and support requirements;
- Identify business, privacy, reliability, and long-term maintenance pressures;
- Still do not directly choose databases, cloud providers, or microservices.

## 5. User Doesn't Know

Input:

> I don't know if I need to save task history.

Expectations:

- Provide specific options such as "don't save," "only restore current task," "save history long-term";
- Explain the consequences of each choice;
- Recommend the simplest default option based on available information.

## 6. Preventing Scope Creep

Input:

> The first version also needs a plugin marketplace, multi-person collaboration, cloud sync, and auto-update.

Expectations:

- Require each feature to justify its necessity for the first phase;
- Check if they can be postponed;
- Place items without realistic basis into Non-goals or Deferred;
- Do not keep all features just for the sake of "completeness."