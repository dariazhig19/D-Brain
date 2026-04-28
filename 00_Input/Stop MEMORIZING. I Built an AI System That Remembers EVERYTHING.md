---
title: "Stop MEMORIZING. I Built an AI System That Remembers EVERYTHING"
source: "https://www.youtube.com/watch?v=JtjfYS9hfWw"
author:
  - "[[Neural Enlightenment]]"
published: 2026-04-09
created: 2026-04-27
description: "🚀 The Wright System — what doesn't make it to YouTube. Get access to the private channel (AI workflows, prompts, cases) → https://link.makeunion.ru/yL4j38📌 Materials and..."
tags:
  - "clippings"
---
![](https://www.youtube.com/watch?v=JtjfYS9hfWw)

## Transcript

### Introduction

**0:00** · Almost everyone who has heard about neural networks at least once uses Notebook LM to conveniently store and process information.

**0:07** · But Notebook LM has a major downside.

**0:09** · Notebook LM is a way to communicate with a neural network about your context, your information. But in this video I'll show you a completely different combination. We won't just collect information into a single database that can later serve both you and the agent. We'll make it so that this information can be edited and fed as skills into Claude Code or regular Claude.

**0:31** · Work conveniently in absolutely different scenarios. And most importantly, we won't have to pay for anything extra. Everything will be available with a Claude Plus subscription and the free Obsidian app. In this video we'll together create a huge knowledge base to get started with vibe-coding. So this video will be useful to absolutely everyone.

**0:47** · My name is Romarey. You're on the Neural Enlightenment channel. Let's go.

**0:52** · So, our task is as simple as possible.

**0:54** · Let's say we're going to learn vibe-coding. We want to learn the very basics, but watching dozens of YouTube videos is sometimes not very productive. So using this exact example, let's now collect everything we need. We have my video about Claude Code. And additionally I've already opened

**1:09** · Claude's documentation. Here too are Claudes, various cases that we'll need. Let's say we collected some articles that can help us understand this topic, find the right skills, find the right documentation and simplify our lives. Usually we had to upload all of this somewhere to Notebook LM or into a note, and then we drown in notes and there's no point to any of it. How many videos and notes do you have in a "watch later" or "read later" folder? There's a countless number from each of us, so this tool will help read for you.

**1:39** · Next, what we need to do when we've prepared the material itself — what exactly do we want to add here? This is the first part and it will also handle analytics. We need to download Obsidian. I hope everyone already has Claude.

### Why You Need Obsidian

**1:50** · Well, Claude can be downloaded too if needed.

**1:51** · Specifically the Claude desktop app is what we'll need today. And Obsidian. What is it?

**1:55** · Essentially, it's a note-taking app. It will look like this. But unlike regular notes, all text information is stored as MD files. MD files are essentially a markup format that is well-read both by Claude Code and by various applications. This also allows us to be maximally flexible in terms of immersing the agent into your system. So that Claude Code can work with your knowledge — that is, with our database that we'll be collecting — we don't need to create any MCP servers or connect Pinecone. All of this

**2:28** · will be directly on our computer, which saves us tokens — but that's not the most important thing. It dramatically increases effectiveness. For now though, I want to share my private club with you. And no, I'm not going to tell you that for just 5,000 rubles you can join. Everything is much simpler. Just follow the link in the description to my Telegram bot and get access to a private community with my system for working with neural networks for 0 rubles. Without

**2:56** · any card attachment, without any hidden payments. Absolutely free access. Every Wednesday a new lesson with my personal use cases of neural networks. For example, how I work with prompt generation for neural networks, how I work with skills, how I create content using neural networks, and many more lessons I plan to record in this private community. Absolutely free access.

**3:19** · There you'll also find my prompt enhancer, materials from all videos, checklists, various presentations and more. All in one place so you can level up your knowledge.

**3:29** · Follow the link, grab the first lesson on the prompt framework as I use it, and wait for new lessons.

**3:36** · Let's now move to the next task. Obsidian is completely free, so we click download and install it on our computer. After installing Obsidian, immediately install two extensions. You'll need the web clipper. This is essentially a browser extension for Google Chrome or any Chromium browser that will add any file or any interesting information to Obsidian with one click, simplifying our lives. That is, instead of Notebook LM, you'll have Obsidian. Here we simply click Add to Chrome and install the extension.

### Installing Obsidian

**4:08** · Now that the extension is added, I pin it, and from now on I'll be able to just click here and save whatever I need. Next we can go to any page. And there we go — a title will be created. Where exactly that page was from, so the agent can read it. Description, tags automatically, and the page itself. We'll be able to add it to Obsidian, or copy the entire page to clipboard, or save it as a file. Then open Obsidian. And here we have several options for how exactly we'll use it. We can create a new vault, open a vault folder, or

### Creating a New Vault in Obsidian

**4:40** · connect iCloud Sync. Today we'll be creating a new vault, so that's what we'll name it. And then I'll name our folder "code". I'll choose its location. It's better to choose a location where you won't accidentally delete it. In my case it will be the Documents folder.

**4:53** · I click Save and create it in this form. Excellent. This application will become our unified knowledge base going forward. Here you can see several tabs that resemble a code editor. Here we'll have our notes, which we can organize into files, folders, etc. Here we have the actual Markdown files — they will be fully editable and the agent can edit them. Here we have the database that

### How the Knowledge Base Works

**5:15** · you saw in the introduction. We'll build it together next. Now we just need to download one more plugin. We'll click on Settings, go to Community Plugins, and enable the ability to search for community plugins. We click Browse. And we see many capabilities to download extensions that can help us.

**5:32** · For example, Kanban — to make a full task management system. For example, I have such a task system for an agent in Claude, and it manages itself during development.

**5:42** · And I can essentially implement all of this here. And it will even be a bit more convenient for the agent because these are Markdown files. Here we have Excel Drive, so we can immediately edit and view what we've drawn. Here we have the ability to work with tasks, copilot. In general, a huge number of things, but today we only need one thing.

**6:02** · We'll type "image" here and then find the "local images" plugin. Essentially it will allow us to use images, as you can see, in our Markdown files — fully, so we have not only text. Now that we've installed it, we close everything and get a folder in which we'll work going forward. We need to go to the Claude desktop app and here we create a new

### Creating a Project in Claude Code

**6:24** · project. In this new project we can either start fresh, import a project, or use an existing folder. We'll use the existing folder, so Obsidian and Claude work in the same location, allowing them to interact with each other. For the name we can write something like "code knowledge base," or

**6:47** · whatever you want, just so you don't get confused. We click Create. And here in our newly created project we paste the prompt that I'll leave under this video. Go to our materials page — the link will be in the description. You'll find materials for this video, prompts, checklists, everything you need to replicate what I'm showing you, plus all materials from previous videos. So, something interesting happens — what did this prompt do? Here it tells us itself — it created CLAUDE.md. Those who have tried any vibe-coding know this is an instruction for the Claude agent. It looks at this instruction first. That's its context. Next there's INDEX.md, our main navigator, a Raw folder, a Wiki folder, and Welcome. That is, this is what we already had. The Raw folder will essentially be our source where we add various raw material we find, so that Claude Code can then interact with it independently. Let's go back to Obsidian and see how this looks now. Here it tells us itself: "Put everything raw here — articles via web clipper, notes, screenshots, PDFs."

### How the Structure Looks in Obsidian

**7:47** · Claude Code takes materials from here, and we'll configure Claude Code to automatically pull from here daily. All you'll need to do is upload materials on the topic here — which is exactly what Notebook LM, for example, can't do. We see that our interconnections are growing. Here we have "Welcome" — let's delete it, we don't need it.

**8:03** · Then here's our CLAUDE.md, which it immediately filled in itself — that there will be raw materials in this folder, Wiki. In this folder, rules for creating Wiki. How exactly this will work, the rules for answering questions. This is first and foremost an instruction for Claude Code, not for Obsidian, not for humans. And there's an index — a quick way for us to navigate to where we need to go. And we see that since these pages are mentioned in the index, we have that branching of our

**8:30** · database. Now we just need to add all the information from our tabs. Let's do exactly that. For this we'll open our Claude Code. Then I'll go to my prompt enhancer and send it information about what I need — that I'll be sending it data and information about vibe-coding in Claude Code, and it would then independently distribute it where needed, work with it, create various

### Preparing the Prompt for Processing Materials

**8:56** · topics. Here's an important point I want to add immediately, since we'll have a lot of content in English — I would add some important context. And let's tell it right here.

### Important Setting

**9:05** · Let's please add to CLAUDE.md that, despite the fact that I may send you some prompts and information in English in this project, absolutely all information, except for professional terms, must be translated into Russian and russified. This phrase will help us work correctly with Claude going forward. Now that this is done, let's see. I think here — yes, perfect, everything is ready. We grab this prompt. Now here it's already created a CLAUDE.md. Let's go back to our project.

**9:34** · Why do we do this in Code? I think it's obvious. But if you haven't watched my video about Claude Code, definitely watch it. There'll be a hint on screen because Code can also work with files on your computer, unlike a regular chat.

### Why You Need Code, Not Just a Regular Chat

**9:47** · Then we paste our prompt here.

**9:49** · First I'll just remove the unnecessary. And we send it to a new dialogue. We immediately go to this new dialogue. And now we take my video about Claude Code. We copy the complete YouTube text — the extension is called...

**10:03** · We copy the entire transcription from this video. Some will say: "You could have just added it to Notebook." Well yes, but the point is that in Notebook LM it just stays there. And a lot of important data gets missed because you won't ask Notebook LM the right questions if you don't know the topic. But here you don't need to ask the right question. Here you're setting up the knowledge base from the start. And that's the main advantage. Actually, we'll also see now how the Obsidian extension works. For now let me just add to our

### Why This Is Better Than NotebookLM

**10:31** · prompt all of this. Now that we've added everything necessary, let's see how the prompt works.

**10:36** · By the way, you can refine this prompt for any topic using my prompt enhancer. Absolutely no difference. A video about how to create prompts, including with my enhancer, is also on the channel. We set the hint here.

**10:48** · Initially it will save the original in Raw, then extract key ideas, patterns, prompts, create and update wiki pages, link them together for your convenience, and update navigation. So, knowing what it will do, we send it this prompt. Let's now go to Obsidian and watch how it creates our connections. You can also watch in Claude Code how many characters it reads and how much it processes in total. And we go back. I'll show this in fast-forward.

**11:23** · So, it made the first one. Here we have a large database in which we'll work going forward. But then I immediately asked it: first, rename files to Russian. Then load all the necessary information you find. And it went to read, view, and

**11:38** · edit on its own. Here we see it started adding content — about GitHub, for example, something that wasn't added last time. Here too about debugging and fixing errors. Here too about subscriptions and pricing, how to work with them going forward. And we can look right now at what it has ready. Even just from what's been done — at this point we have the Raw itself (the draft information) and our Wiki, which we can now

**12:06** · enter. For example, here we have information about automatic memory. We can see what auto-memory is. A built-in system that automatically saves notes and context between sessions, its key ideas, how this memory works. First session — what needs to be done

**12:22** · going forward, etc. And here it immediately gives us an instruction and links between them. Best practices, how you can use memory — this particular example. Then here we can also see how to use skills. Which skills will be needed here, it'll tell us too. So here we have quick debugging, how it'll look with skills. Chain of skills in the required format. Well, I think you got that already. Then it needed to finish, and it updated everything that was needed. We see that it even set itself

**12:54** · tasks for how it would finalize things. After which it's now updating navigation and doing verification to check the completeness of all the information. Okay. Here we see it already even ran out of context at 1 million tokens. That's fine. In our case we've practically finished everything already. And here the agent performs

**13:13** · more of a technical function. It doesn't really need much prior context. It will go into our Obsidian anyway. Now while we wait for it to finish, let's look at how the extension works. You're just browsing the internet, find anything you want, and literally a button appears right here — "Add to Obsidian."

### How Web Clipper Works in Practice

**13:30** · You click "open application" and it's done. Here it is. But here it will be added separately. So in our case we'll right-click, and then we can for example click Show in Finder and simply move it — we see it created a separate "clippings" folder in this same folder. So our task will be to do the following. To stay within that folder — that's fine — we'll need to go to Claude. It'll finish for us shortly, but we'll give it the next prompt. Also a new "clippings" folder appeared with those links from the

### Setting Up a Separate Process for New Clippings

**14:04** · browser that I save on this topic when I see something interesting. Please give me a prompt for Claude Code for a separate dialogue within this same project, in which it will do the following: it will independently, every 2 days, check the Raw folder and the Clippings folder and update my knowledge

**14:21** · base from them, so all my information stays current and notes don't get lost. That is, we're literally teaching it right now to sort through the clutter that we usually accumulate. Or just forget about what we wanted to add, wanted to watch, and it ends up coming to nothing. We see that it independently figured out to update CLAUDE.md. Now the agent will always know we have such a folder. And now it immediately creates a processed files log. Then the prompt we're setting now. Automate this scheduling feature. And literally you'll have automation — for 0

### Automating Knowledge Base Updates on a Schedule

**14:53** · rubles. If you already have a Claude subscription, you don't need anything extra — no additional knowledge, no complex programs, no API keys. Everything will work within a single ecosystem.

**15:03** · We open our prompt. It looks like this. We copy it completely. Now we go to our project. Then we go to creating a new dialogue. And here we see our schedule which we can change. Here we have a schedule for other tasks that we don't like. We'll create a new one now. Let's call it "Obsidian information processor." That's just the description we need.

**15:27** · Or just "information processor."

**15:29** · We paste the prompt, set a daily schedule at 9:00. Click Save. Now we see that within this project, this will be launched on schedule. I can show you now how this will look in command form. We just go here. And then every morning at 9:00 Claude will independently process all our notes that were saved. This can be set up for any topic you're interested in. The result we'll see is that this won't just be

**15:53** · information like in Notebook LM — it will be immediately processed information that we can work with, in which we can maintain a huge database and knowledge base both for our agents (not just Claude Code, but Code for any purpose), and for ourselves — which is very easily editable, very easily assembled, doesn't require a huge number of tokens — we spent one million tokens on everything, which is not that much for a Claude subscription. And as a result, we get a universal model available for everything.

**16:24** · Thank you very much for watching this video all the way through. Link to my private system is in the description. And the last video is available here from the on-screen hint. See you.


<!-- [[Daily_Report_20260428]] -->
