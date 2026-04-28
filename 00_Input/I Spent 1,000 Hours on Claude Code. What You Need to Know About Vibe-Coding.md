---
title: "I Spent 1,000 Hours on Claude Code. What You Need to Know About Vibe-Coding"
source: "https://www.youtube.com/watch?v=sx6ZSbc51gY"
author:
  - "[[Neural Enlightenment]]"
published: 2026-04-03
created: 2026-04-27
description: "🚀 The Wright System — what doesn't make it to YouTube. Get access to the private channel (AI workflows, prompts, cases) → https://link.makeunion.ru/DgYg9e📌 Materials:–..."
tags:
  - "clippings"
---
![](https://www.youtube.com/watch?v=sx6ZSbc51gY)

## Transcript

### Introduction

**0:00** · Over the last few months I've spent more than 1,000 hours in Claude Code. I built two fully-functioning online services from scratch — one already has paying users, and thousands of people use the other. And most importantly, when I was just starting to learn vibe-coding by watching YouTube videos, I genuinely thought I would never be able to use this tool. All these incomprehensible terminals, commands you need to enter, things you still have to do in the code somehow. But in reality everything works differently. And in this video I'll show you how to use Claude Code to its maximum potential without any terminals,

**0:29** · without needing to write commands, and I'll show you truly effective tools that will improve your codebase and make your product much faster and more efficient. By the end of the video you'll have a task management system like this one, an understanding of how to create documentation, Claude settings, working with context, and everything you need to create your first product.

**0:48** · So be sure to watch this video all the way to the end. My name is Romarey. You're on the Neural Enlightenment channel. Let's go.

**0:55** · First we need to dispel all the myths that exist in vibe-coding. I created my first app back in November, but before that, while I was playing with code in ChatGPT and so on, I constantly saw comments saying that neural networks can't do anything beyond a simple calculator. Literally on my last video someone wrote that your project won't even hold up when you have one user per second, and so on. And when you see this, understand one thing: it's flat-out lies

### The Main Myth About Neural Networks and Code

**1:20** · from people who are either incompetent themselves, or simply expressing opinions based on the old thinking about how things worked a year ago or more. Let's take my service Koneo as an example — you can buy it, pay for it right now. It was created in just one month. In one

**1:39** · month from idea development to final implementation. There are real users there today, there are payments and so on. But Koneo isn't even my main service — because AI has simultaneous users constantly around 100 at any given time. There's an extension tied to the app. The app has Telegram, users, their marketplace stores. Everything is synced. And despite there being 1,700 users total, 260 of them have active syncs, we have a great admin panel, a large number of integrations, a great UI. All of this was created by one person — me — over the last month.

**2:13** · So when someone tells you fairy tales about how neural networks can't do anything, just visit Koneo or ULIP AI and see that they actually can. Now let's move on to Claude Code itself. When you hear that phrase, it's not entirely clear what it means if you're a complete beginner. There's a model in Cursor, in Anthropic there's Claude. And what exactly is the real Claude? It's essentially a model, but there are many wrappers

### What Claude Code Actually Is

**2:37** · available. In this video I'll of course tell you about the ones I use myself, because I've tested almost everything and simply chose the most effective method. The first thing that comes to mind when we talk about Claude Code is, of course, the Claude desktop app.

**2:49** · You just go to the Code tab here, and you get the ability to create some projects. We can see I used it quite actively for some time, but it has a lot of downsides. Yes, we can also choose our branch here. Here we can directly see that I have some projects — that same ULIP AI and Koneo — but there's no terminal here. There isn't even a proper file system. It's a simplified thing you can use if you're going to do something simple. But for full-scale development using the Claude desktop app, I

**3:17** · personally wouldn't use it at all, because the logic of Claude Code is specifically that it can manage your files, manage various integrations, and so on. And here that will work poorly. So there are a few more options.

**3:30** · The main setup I would recommend today is the integration of Claude Code directly into VS Code. Essentially, VS Code is a code editor, and here's what's important to understand about Claude — this isn't the old story where it would write code and you'd have to paste it somewhere. Claude Code is essentially an agent

### The Best Way to Work With Claude Code

**3:49** · that will do everything independently for you, knows your directory, knows your files, and works with them. And VS Code is an editor used by both vibe-coders and programmers — you can connect Claude here where they show Copilot. So you just click here. This is a completely free application. And after that you'll be greeted with this interface. Let me say a bit about VS Code itself, because it's an essential part of vibe-coding. The system

**4:15** · for managing this code, the file management system. When you open VS Code, you need to understand a few things. VS Code essentially works with directories that contain your project. For example, we can see I already created a folder called My Project. Let's create another one now — let's call it My2. That's the folder where our app, landing page, or

**4:36** · whatever we create will run going forward. That's the folder where the agent will work. To open this folder, you can click Open here, or create a file, then Open Folder. On Windows it might look slightly different, but the logic is identical. We select our folder here. Go into it. It's a completely empty folder, but that's fine. And here we just click "I Trust." Important: when you choose a directory, try to make sure the path to that directory contains no Russian characters.

**5:03** · You can check this pretty simply.

**5:05** · Right-click on the folder. Then go to Properties. And we can see that in my case the desktop is written in Russian on Mac. And most likely there will be some issues. So when I, for example, create projects not for video but for myself, I just put the folder in Documents. Documents on Mac is in English, so it's much easier to work with everything there. And the folder shouldn't be named something like "My Projects" in Russian — try to name everything in English.

**5:29** · After you create the folder here, you essentially get this workspace. Just to clarify — you won't need to do anything in the code at all. In all the time I've been creating my second service, I haven't touched the code manually once, except to add keys. Even some

### Why You Don't Need to Write Code Manually

**5:45** · text I didn't change by hand, because it's much easier to do with the agent — and it won't break anything. Essentially this folder will only be useful for finding documentation and such, but it's completely useless otherwise since we won't be working with the file system manually. Then you can see that I already have Claude and it's nicely connected now, and you can create new sessions and so on, but that's not how we'll be using it.

**6:09** · So go to Extensions, type "claude code." If it's not visible initially since mine is already installed, type "claude" and choose the Claude Code for VS Code extension. Essentially, this extension will allow you to use the model available on your subscription

### How to Install Claude Code in VS Code

**6:28** · inside a third-party application — VS Code in our case. After installing it, you'll be able to open Claude Code right here on the right side. We press Command+Shift+P. On Windows it's Ctrl+Shift+P. And then here we need — in my case it's already in recent since it was used last.

**6:48** · In your case you may need to type "Claude Open new tab" and "open terminal." Important note: what you see here is because I'm in Claude already — you'll just see a "Sign in to Claude" button. And you'll just need to sign in with your Claude account, because Claude Code and Claude are the same subscription. And then that window opens for you.

**7:07** · Let me open both and show you on concrete examples how things work. Most of the time when someone shows you Claude Code, they almost always show it in this terminal, where you need to press something, type "y" and so on — and the terminal scares off most people.

**7:24** · The terminal scared me, the terminal looks like something daunting — something that, if you're not a programmer, will be hard to learn and hard to use. And that's essentially true, because the terminal gives you some discomfort. There are no convenient settings options. There are no convenient interaction options.

**7:44** · So when someone shows you that you need to use Claude Code in the terminal, tell those people to take a hike, because it's simply inconvenient. Again, maybe when you're a programmer who understands code, the terminal helps you work slightly better in Claude Code. I don't know why people use it that way, because it's super inconvenient, but everyone seems to show it in videos. Sometimes I think it's because these people have never actually created any projects and just found something for the video and everyone copied each other. We will never use the terminal — not today, not ever — because I've never once used the terminal. And even Claude Code inside the regular Claude desktop app is better in my opinion.

**8:18** · But even better, of course, is the extension, which will work just like a regular chat but inside your project.

**8:23** · Essentially now Claude Code is open in one window. Here you'll have your open file, and then you'll have Explorer — everything that's in your folder. Today we'll create something more complex than a simple landing page, specifically to dispel all those prejudices. But we don't have a lot of time. In an hour we'll need to create a small application. And what we're going to do now — let's see how this will work. I'll type "create an HTML file" — Claude Code works on a dark background. And then here

**8:54** · I'll have some settings. Clicking the plus signs, I can upload a file — for example, a picture to show it where it went wrong. I can add context, and additionally use search.

### Work Modes

**9:04** · That is, the chat can work here as a regular chat. "Ask before edits" exists specifically for that purpose.

**9:09** · For example, use "ask before edits" when you need to first study your project, understand that Claude understands everything correctly, make sure nothing breaks, and then confirm the changes. Auto-edit will obviously work automatically — it will study and change things itself without asking you. And Plan Mode is for large tasks. For example, when I add some functionality to ULIP AI, I first prepare a large research prompt, we run it together.

**9:37** · Then the prompt can be like 10 A4 pages covering all the functionality at once, because Claude is smart enough to do it in one prompt. And then I send this large prompt here, but always in Plan Mode so it confirms it understands what needs to be done. Then you have Effort — this is the intensity of how Claude will think.

**9:53** · Look, by default "high" is almost always enough — just a bit above average. And when you need to create a project, you'll understand that choosing slightly lower for simple tasks is fine — changing a button or something. First, it'll work faster; second, it'll consume fewer tokens. But when we talk about Claude for professional work — for example, I have a $200 subscription, and over 3 months I use it for coding probably around 8 hours a day. When I'm creating something, I genuinely do 8-9 hours of work time per day.

**10:23** · I only ran out of weekly limits once, and even then I just waited a day and everything was restored. So there's no issue with tokens in Claude if you work professionally.

**10:31** · And when you work professionally, that essentially means instead of, say, a development team — I had an analytics service and we built it with programmers, so I know exactly how it works both with people and with neural networks — if previously I was paying around 300,000 rubles in salaries just for development, today I pay Claude $200 for Claude Code, plus sometimes tokens go up to $100, so it's around 25,000 rubles. That suits me completely. But when we're talking about wanting to code with a

### How Much Development Costs Through Claude

**11:01** · limited budget, for these cases you need to be economical, because even on a $100 subscription tokens will run out. Right now we'll just choose slightly above average. And you can see that we haven't actually found where to choose the model and so on.

### Where to Choose the Model (Opus / Sonnet)

**11:16** · So we click here. And what happens through the terminal — here we have the option to choose which model to use. I always default to Opus 4.6 regardless of the task, because again when you have a large subscription it's enough. For simple tasks you can use Sonnet, but you need to understand that what Opus does in one prompt, even Sonnet will take three or four prompts to do. And that's just basic time savings. Here you can choose whether to use the thinking model or not. Always leave it enabled.

**11:42** · Here you can see how many tokens you've spent, etc. Everything above that we don't particularly need. That is, here you can basically clear a dialogue and so on. We don't need that, because essentially all dialogues will be visible here. As you can see, it's not showing all of them because it only counts dialogues that were within a specific directory — that same My2 folder. If I now go to

**12:05** · another directory, I'll see my dialogue history for that one. And it's incredibly convenient because everything is organized by project. And clicking this plus sign, you can create multiple agent requests simultaneously. For example, you might have a code audit running in one window — because many people write in comments like "you don't know what refactoring is" or some other nonsense. But first, practically anyone knows what refactoring is, because Claude itself knows how to do it. And essentially when you're coding you

**12:32** · practically every day create an audit in a separate window — what dead code you have, what refactoring is needed, where speed can be optimized, where there are large files, where something in UI/UX was done illogically. That's quite a large task. You create it in a separate window, then switch to another. And here you continue creating code. Let's now paste our simple request and send it to him. And we see that he created our project. And here appeared

### Creating HTML

**12:58** · the HTML file he made. And here comes the first moment when we need to somehow run this. And most of the time people get stuck here. Usually you need to open the terminal through "New Terminal" and type something. But I still barely know any terminal commands, because they differ depending on which programming language you're using. So here, when we've made some code, we tell it: "Run a dev server." Accordingly, it will now open this page in the browser. If you're using the Cursor shell, there's a browser right in Cursor — in VS Code

**13:28** · you can do that too but through an extension, and we won't do it that way because it's simply longer and extensions work poorly. We see that it did it in Python. We see it's launching, checking which ports are occupied by other projects, so it does it again on a different port. And there — our first page is ready. And here we see this page in the browser. Moreover, if we change something on it — for example, here we type "cloud" and want it that way — we go back, refresh the page, we see

**13:59** · that it updates, and we can quickly make changes to our site this way. Essentially this is the first basic part — he changes files himself, he'll manage your file system on his own, and so on. He will, however, need certain additions for that. We'll go through all of this now — how to make CLAUDE.md, how to make project documentation, and everything else. Just one important note:

**14:18** · this code — don't touch it at all, even when you just need to change some text. Don't go in there, because there's no point. Yes, obviously if you already know code that's great, but here it's important to understand one simple thing: in any case, in six months or a year, knowledge of code won't

**14:35** · be needed at all. Well, it's essentially already not needed. But obviously if we're talking about very large projects with tens of thousands of simultaneous active users, there might be some issues. But my project isn't like that yet. My project has 200 active users simultaneously and 1,700 overall — active in the sense of being in there — and it's all fine, everything flies, everything works as needed. Essentially, those who know code are actually at a slight disadvantage, because you always want to tweak something by hand. You always think you know better, even though that's not always the case, and you actually waste time. Speed at the moment is often more important.

**15:07** · Now let's completely close this tab, leaving just two: Explorer and our chat. Now that we've created our first project, we won't stay in it. Let's click Open Folder again. And let's go to My Project, the first folder I created. Let me create a similar one. Let's open Claude Code here again. And we see that yes,

**15:26** · there's nothing in the history, because this is already a new project. To create some simple application going forward, no, we don't need to plan it ourselves. First you should plan it in a regular neural network. Let's use Claude as an example — let's go back to chat and look at, for example, how I run project pre-development. That is, accordingly, the project where we do all the development. Here you can see that chats are broken down by various topics. There's, conditionally, some bug diagnostics, data exports, errors, other things. Here we have

**15:55** · some complex task optimization, a comprehensive site audit, for example. Everything is broken into separate tasks. And here, as you can see, there's a huge amount of documentation. That is, when I come up with some functionality, Claude knows absolutely everything. Why don't I do it, say, right here in the code?

**16:11** · Because, in my view, there should still be two brains. One brain handles the planning and has no access to the codebase, so nothing accidentally breaks while you're planning — you just want the task done. And the second brain is that same Claude Code inside VS Code, which handles the actual implementation.

**16:31** · And I would not combine these things in any way. I wouldn't try to do everything in one place. So essentially we become like managers, passing messages from one to the other. And let's say we make some project.

**16:44** · Let's make it comparatively complex, but not so it takes us 5 hours. I'll call it a personal CRM. Many of you watching this are freelancers or working on projects where you need to keep track of things.

### Building a CRM

**16:57** · Again, a personal CRM. I have a simple one myself. It's connected to our Telegram bot so the bot sends various messages to clients depending on the stage.

**17:08** · Works perfectly. Stopped paying for an external solution. And besides that, customized it for our needs — specifically what I was missing, like Telegram automatically sending certain client notifications. Now that we've chosen a project name here, let's go into the project itself. First, of course, there'll be nothing here, but now we need to create our first prompt. I use my prompt enhancer — the link will be in the description, it's completely free. And I tell it the following. Look — I'm a freelance marketer working with clients in different niches, and I need to

**17:37** · create some kind of CRM and task manager using Claude Code for myself. Right now I don't really know what I want. I'm ready to answer some questions that will help it think through the detailed logic, and from you I want a prompt for Claude where in one dialogue it will first ask me all the necessary questions to help it think through the ideal UI/UX for this project. I will only use this CRM for myself.

**18:03** · I might use some simple to-do lists there.

**18:07** · There should be a nice UI. And most importantly, I initially plan to use this on a dev server without deploying to an external resource, keeping it local. I'm waiting for that prompt from you. Here you just speak out a jumble of chaotic thoughts.

**18:19** · What exactly are you trying to achieve in your development? What's the overall goal?

**18:23** · It's fine if it's rambling. I'm specifically showing you the same thing. Although for complex projects the process is of course different — first there's research on the internet, then an agent in the browser, etc. But this is how I started when creating small personal projects. And then here it creates that very prompt for us.

**18:41** · The prompt will be very large, and that's correct, because it will include everything we may have forgotten. We can even look here. It says: "Ask me the following questions — five to seven questions per block. Think through the design system."

**18:55** · Then we continue. Well, in principle that's it — think through the design system, think through the UX system, how everything will work. We copy our prompt, paste it here, then write "I'll respond in Russian" and send it to Opus 4.6. Excellent. And now it's asking us questions. I often use ChatGPT including for voice input to avoid errors. Look — my clients are small businesses. I help

**19:17** · companies grow through targeted advertising, contextual advertising. I sometimes help companies create websites, plan advertising campaigns, work across different niches — usually mixed together. But let's say my main niche is HoReCa. How many active clients do I have simultaneously — around

**19:33** · fifty, twenty of whom are dormant. And maybe around thirty could come back. Do I track leads? Yes, I communicate with new clients daily and try to set reminders and so on. What stages does a client go through? Well, first I have a base, then I communicate with the client, then I make an offer, then we sign a contract, we do the work. Then we have

**19:56** · project completion. Well, actually even upselling — trying to extend our engagement. Do I need money tracking? Yes, let's do it. That'll be cool in a separate tab. And how clients come to me now — mostly I find them myself on Telegram. Of course I'm giving roughly what comes to mind, because this isn't really about me, but the basic logic will be approximately like this. And then going forward he

**20:20** · independently thinks through everything we need. He considers everything and then asks the second part of questions. How do I currently manage tasks — usually I keep tasks in notes. What types of tasks do I have? Well, everything I mentioned. Then tasks linked to clients — of course, general tasks also happen but rarely. Are there recurring tasks? Of course. Do I need deadlines and priorities? Of course. And are there projects within a client? No, there aren't.

**20:47** · So he asks me questions I might not have thought of initially — finances, recurring tasks. Obviously in reality I've thought it all through, but when you're doing this for the first time you might not think about all of it, because it's too much logic in one place. Previously you needed entire teams of people doing research and so on. Now you can do this for yourself in 2 minutes. And then daily usage. I'll

**21:14** · work with it constantly, open it every morning, and work with tasks throughout the day. What should be on the main dashboard? Design it yourself to be maximally efficient. What actions should be fastest — one-click? For example, adding a task definitely one click, writing a note one click, moving a lead to the next status with drag and drop. Do I work alone at the computer? Yes, at just one computer. No need to set up server integrations right now. We send this to him again.

**21:41** · Just to clarify — drag and drop is when you can drag cards from one place to another. It's called drag and drop. And our interview continues further. What information do I store about a client? Again — company name, client card, name, phone, Telegram, email possibly, website, city. Then.

**22:03** · Do I record communication history? No, I think that's unnecessary. Comments will be more than enough. Do I need files per client? No, not needed. Do I need categories and tags? Well, a tag could work as an option. That is, exactly for categorization purposes. Do I have the concept of a deal? Well, essentially a deal is

**22:23** · one month of work, for example, some kind of management or website creation. We paste this here. Then I answered another question about the server, if you want to pause to save your time. And then he asks us about design — how it'll look and so on. Here's my main advice — just go to Dribbble. It's a site where all designers share their interface work. Essentially a portfolio. And then let's write here "task CRM" or something like that — something

**22:49** · like what we're creating now, to find a design that's roughly what we'd want for our future app. And we check what we like and what would suit us.

**23:01** · For example, I'd want to see something like this. I just copy the image now, go back, and tell it: use this reference as the basis when thinking through the UI/UX.

**23:12** · Essentially it should become your main answer. When you're making something for yourself, design isn't that important, so it's enough to just reference a reference. When you're making products for clients, you usually start by creating a UI kit — here's how it looks — and then based on that UI kit you and the agent think through the entire interface. Then we have technical stack limitations. Just to clarify — there are many options for which programming language and so on you can use to accomplish any task. I've even

### Why Next.js Is the Best Choice

**23:42** · tried some languages you can use. But ultimately, if we take the language that neural networks understand best, where you'll have the fewest problems in the future, which is easily scalable and you won't have to redo everything from scratch later — even though it might seem a bit complex at the start — that's Next.js.

**23:59** · We always build everything with it now — any products, both for ourselves and for external use. After that you can buy a subscription. And the database honestly doesn't matter much — what exactly will be used.

**24:09** · This will be a local database. So we can say SQLite. Then am I comfortable running things in terminal?

**24:15** · We can just say yes. Comfortable.

**24:19** · And then choose SQLite again. And also whether offline work is needed. Sure, let's say yes. Here, if something is unclear at these stages — when you're creating for yourself, not right now but in general when you'll be creating the same things — you just ask it: "How does SQLite work?" Well for example, to make sure we don't create a mess. How will this work? And in that way you also

**24:41** · level up your own knowledge, and in the future it'll be much easier. Because when I was starting out I didn't even know you need to do a local DB so nothing accidentally breaks. And I always had the production database breaking things. Everything still works to this day.

**24:52** · Now I use Docker so I can develop inside it first, to make sure nothing breaks and so on. But that comes with time.

**24:59** · You don't really need that at the start.

**25:01** · And there — it tells us everything about how it'll all look and work. So I then send it answers to all the questions it asked me earlier. And then it continues grilling us with questions. And that's good. It's fine that this is taking time. The better you think things through at the start, the easier it'll be later — both for the agent to create the code, and for you.

**25:22** · Because compare: what if we had just written "create a CRM" — what result would we get and would it be tailored to us? Or when we went through that 50-question interview, which may seem tedious but the agent will know literally everything. And now it's creating our system design. Here it's talking to itself, reminding itself of everything we'll be doing. And now our design system is ready. It's thinking through for us how all the fields will look, everything that'll be made. And

**25:49** · I'll say in advance that I usually don't even read this, because if we start editing it now it'll take forever. It makes sense to edit later when it creates some larger mocks.

**26:00** · Validation, what's missing, and everything else. I type: All good. Excellent. And now it tells us itself that we'll build this in stages. And then you tell it: first you can create a visual UI prototype, but I wouldn't even do that. And here we just tell it: Look, I already have a VS Code directory open, Claude Code extension connected, so give me sequential prompts for what I need to do. And now it

### How to Pass Prompts to Claude Code

**26:24** · will create prompts that we'll simply relay here. And then our work will literally be in these two windows. I almost always have them open. We copy from here, paste there. It did something, we copy its response, paste it back. That way your Claude knows the full history and all the nuances, while Claude Code receives fairly clear

**26:41** · briefs. Like in the case of an employee — we have a project manager, product manager, and we're more like a salesperson who came in, said what they want, and now you handle it. That's roughly the same dynamic here. And here it starts creating these sequential prompts. It immediately shows that we'll be creating a Next.js project. Sometimes you'll be shown how to do it manually, but I don't see the point of that honestly, simply because the agent can do it too. Then here — it will automatically through your terminal, without

**27:14** · your involvement, install everything it needs — extensions like Prisma client, various UI kits, I gather. Here we have React — one of the languages. Here we have SQLite which it will install itself. So our prompt is ready. It actually gave us two prompts here. Oh — it gave us eight prompts. And honestly,

**27:34** · when you're doing something for yourself, you can be lazy and just copy everything at once. And when Claude started slowing down — maybe when you're watching this it's no longer slow, because March 27, 28, and 29 are exactly the days when Claude

**27:49** · deliberately downgraded their models' performance to handle the load. So if we copy this whole huge document at once right now, obviously nothing will happen. But usually I actually do this and everything works fine. When we have this many prompts, we just go here. At this stage I usually set it to maximum thinking, because it'll be a bit more stable. It's important to understand that the architecture that gets established at the beginning of your application — not the functionality itself, like the CRM task system, but the architecture, how to set up Next.js —  the framework

**28:22** · the language is written in — how to set up the database and so on — will directly affect speed and stability so nothing breaks.

**28:29** · So here it's better to choose models that think longer. We send our first request. The first thing we see is that it started installing the Next.js framework.

**28:36** · Actually, it's much simpler to explain what Python is — I think everyone's heard of it in ads. Well, Python is essentially a competitor in terms of the framework you can use to create things. It went to do this in a large volume. Let's wait for this to complete. And here we see that even though this isn't Plan Mode, it sets itself tasks for what

**28:55** · it will do. All the schemas are created. We can already go look at our folder. And he's already structured the directory for us. CLAUDE.md appeared, which we'll review once we've run all these prompts. Here all the project files appeared — Ritmo for deployment, some public pages appeared. Here we have Next.js logo files,

### What Gets Created Automatically

**29:13** · files, and .env appeared. This is accordingly where we'll insert secret variables — that is, any API keys, any additional variables for the code that later, when you, say, deploy the project (upload it to the internet), are stored not in the code but for

**29:31** · security purposes are stored in the place where you deployed the project. For example, Railway or Timeweb if you're in Russia. But for now I want to share my private club with you. And no, I'm not going to tell you that for just 5,000 rubles you can join. Everything is much simpler. Just follow the link in the description to my Telegram bot and get access to a private community with my system for working with neural networks for 0

**29:54** · rubles. Without any card attachment, without any hidden payments. Absolutely free access. Every Wednesday a new lesson with my personal use cases of neural networks. For example, how I work with prompt generation for neural networks, how I work with skills, how I create content using neural networks, and many more lessons I plan to record in this private community. Absolutely free access.

**30:19** · There you'll also find my prompt enhancer, materials from all videos, checklists, various presentations and more. All in one place so you can level up your knowledge.

**30:29** · Follow the link, grab the first lesson on the prompt framework as I use it, and wait for new lessons.

**30:35** · Now let's move to the next task. And now that it's done, it sends its little report that we asked for in the prompts earlier. Well, Claude gave this in the prompt so it would give us a report at the end. We can copy just something specific. I usually copy the entire dialogue history. Important to check that no keys got in there. For this purpose a rule is filled in CLAUDE.md later. And we send this here. As the first prompt is completed. Usually at this stage it looks at whether there are any errors, maybe somewhere the

**31:07** · agent went in the wrong direction, and immediately steers it in the right direction.

**31:12** · We can immediately move to the second prompt. But before pasting it, add this line at the beginning of the prompt so Claude Code takes into account your current stack. So again we see — it does its thing. On the question of whether to continue in the same dialogue or a different one — actually

**31:30** · there's no big difference. When I'm creating one big task, I try to stay in the same dialogue, because the context will be remembered. We send again and let's continue. To avoid going through all this back-and-forth and boring you, let's just do it. And by this point I managed to run five prompts. That's enough to look at the first things — our first project that we created. For this I can either use the terminal, or simply write here "run dev server." And then

### First CRM Result

**32:00** · we see that port 3000 is occupied, so it launches on 3001. We'll fix that so it works more easily in the future. Let's now open our application. Not everything is working yet, but some first features are already working that we can look at. First, when we go to Clients, it all sorts calmly like this. We can click on a specific client. His card opens. We can enter

**32:26** · comments about him. We can edit the card. This we'll fix now, it's fine. And editing isn't working yet — not done. Here we see formatting errors. This was added to the code when they lowered the model intelligence. And now there are significantly more errors. We can type there "test" for example. Here are our deals. Here we have tasks

### Interface and Features

**32:46** · — it says there aren't any, but that's because tasks will be separate. That's how our mini-CRM looks. Honestly — I'd say it looks really cool. And I can't point to anything that's bad here. To me everything looks super. From here you can go to a client. We still have unfinished tasks and

**33:05** · revenue, so this plus button doesn't work yet. But we already have the first part of the application ready. That is, we can now stop paying for something external and use our own. All this — from the time I started recording the video overall, one minute has passed, and we already have this great version. And it still hasn't made the mobile version and everything else — but that's literally five prompts. Who would have thought that in five prompts we'd have a whole CRM ready with everything

**33:30** · we need. Now let's talk about some important things you also need to know about Claude Code, because you'll be able to run prompts on your own without me from here. But some important technical things definitely need to be explained. First, if you're working on JS, it will show you various errors you have. This is Next.js where there's already a copy button, so you just copy them, scroll through like this and see that there are quite a lot of errors here.

### How to Fix Errors

**33:52** · When an error appears, you quickly go back and say "fix errors" and paste from there. It doesn't see this, but Next.js in the application will show us. These aren't the most critical errors, because otherwise everything would have crashed, but they exist, and we can fix them right away.

**34:11** · We click send. And after it fixes them, you can even do your own tasks in parallel — go to a new dialogue for example, do something there, etc. You don't have to stay within one dialogue only. For example, while it's doing this, we can copy the prompt for creating the revenue page, click Auto here, and meanwhile

### Working on Tasks in Parallel

**34:31** · check in parallel here. As I told you, while it's doing all of this, there are a few important files in your project files. I'll explain using Next.js as the most popular — these are files you always need to be aware of. The important files you need to know in the project and work with are: .env, .gitignore, and CLAUDE.md. Let's go through them from the beginning.

### Important Project Files

**34:54** · I already talked about .env — essentially how .env works. Various variables will be added here. For example, if today I want to connect the OpenAI API to our project, that OpenAI key will be here. But again, I don't create this manually. Usually the agent creates like the first part for me — what can be added as a variable — and then I refine it.

### What .env Is

**35:18** · Sometimes in projects where high privacy is important and you can't let the agent into your variables — for example, corporate development — you just set such restrictions for Claude. We don't have those, so we don't do much here.

**35:30** · Then .gitignore. In the scope of this video we're not uploading the project to a server. Although I'll also talk about how to do that and through what by the end of the video. But here essentially you specify what exactly should not be added to Git and therefore be ignored. Since we already created the project through my prompt enhancer, since it said this from the start. I'm sure that if we now write gitignore here.

### What .gitignore Is

**35:55** · No wait, it figured this out later by itself, because there's nothing here. Here it added this itself later. But my advice regardless — always copy this from .gitignore, go here, paste it, and write something like "here's my .gitignore — what other files could we add here for security reasons." Since Claude also knows

**36:15** · what's in your project — it has these prompts and so on — it can suggest things, or you could even just ask here as well. Lots of options. I try to keep the conversation here regardless. And we see that for my project with SQLite and Prisma, it says: "I need to also add these items." But remember our concept — we don't do anything manually. So if it writes something like this, we tell it: "Give me a prompt for the agent." And it'll give the agent

**36:40** · the task itself, so it implements all of this. In the meantime the errors are fixed in one place. Let's immediately go here, switch to edit mode. Ready immediately. Then it will itself — we can even go in there — update this very gitignore and add everything needed there, because we want nothing to be needed from us. Well, it even highlights what was added. We've sorted that out. And then there's CLAUDE.md. What is CLAUDE.md? It's essentially

### How to Automate Changes

### What CLAUDE.md Is

**37:06** · context for your agent. This context stores all the main rules, so that every time you send a prompt, the agent first takes your prompt — what you're telling it — and then goes to CLAUDE.md to check what else it needs to consider.

**37:22** · For example, when I develop ULIP AI, my CLAUDE.md, in addition to various technical things, has pre-prepared main rules for how we build design, what UI, where to find it, what rules, what fonts. For example, for email campaigns — in my CLAUDE.md is described where to get the email campaign template if we're doing something automated, how my stack works, what important nuances I have, what things to avoid, what things to do, etc. So usually we do a couple important things together.

**37:53** · Please now create a prompt for the implementation of CLAUDE.md. I really want this prompt to specify: how we run the local server, what our design rules are, what our UI/UX rules are, what technical rules can be added. Suggest these yourself based on what you know about the project, so the agent has an easier time writing code. That is, as you can see, I'm not even giving you anything specific right now. However, in the description

### How to Set Rules for the Agent

**38:18** · under this video, in the materials I'll share, there will be an additional checklist where I'll include everything I told you in this video, and I'll also add a couple of rules from my CLAUDE.md that I insert into projects — so you don't have to guess. Now here, there's actually another important moment — it uses skills that are loaded for me. For example, I have a skill for creating prompts for Claude Code, so it might differ slightly. And then here it gives me this file. Why did it write the file directly rather than a prompt? But okay.

**38:47** · We click the plus and tell it: "Think through and create CLAUDE.md." I do this because it sort of initially sent not quite a prompt, but immediately the ready-made content we'd be working with.

**38:58** · And by the way, let's immediately look — let's send it what it just gave us. Technical stack, critical stack features, what to keep in mind, what colors, tags, and so on, keys, data model. Well, in general everything we need, yes. And additionally immediately a checklist before finishing a task — what needs to be done. Well, now it'll show us who creates it. And essentially we'll have all the critically important files configured. Here's our CLAUDE.md file that it updated.

### Finished CLAUDE.md

**39:28** · Just to clarify — well, 500 lines of that is more than enough. In my projects I actually try not to exceed 300 lines. Not because I'm saving tokens, but because the rest of the documentation goes separately. Let's talk a bit more about documentation, because CLAUDE.md is not created for that purpose, and by default

**39:46** · you won't have documentation here — but documentation is important so you can, for example, upload it to the agent here. Or for example, if your project grows and you want to hire someone, they'll need documentation too. So right away, when you've made your first version — which, by the way, we can see what else appeared here in 20 minutes — the ability to add a client appeared. Immediately the ability to see our latest notes about the client appeared.

### Final CRM Result

**40:11** · Clients, pipeline — that was all there. And even revenue by month. We can now add deals and manage our finances. All of this — 1 hour 32 minutes from the start of recording the video. Here I don't know — search still isn't working here, but again a couple of prompts and we'll finish it. Now let's sort out documentation, and for that I tell you the following. Now also create for me a prompt for creating a project documentation file. There will be a separate large file with everything the agent and developers will need — all the details. And I immediately specify that in CLAUDE.md, in that context

**40:43** · of rules for the agent, add a rule to immediately update this file after any changes. So it's always current. I could copy it, send it to any neural network, and it would immediately know what's happening in my project. And we see that in this prompt it independently says to create a docs folder for us, which will have these project.md files.

**41:00** · This works exactly the same in my real projects — both for clients and for myself. It's quite an important component. Let's send this. So our documentation is ready. Here it specifies what exactly was added to it. We go in. And it's already quite a large file — 1,000 lines — considering we only did five prompts, and something is still being done in the process. I intentionally try to keep refining the project during these segments.

### How to Create Project Docs

**41:26** · And there — we even have a task manager ready. Looks cosmic. Everything is done very nicely. We can create a new task, delete, edit, mark as done, and so on. Everything moves again. Yes, we spent one prompt on this, and we have such an impressive, fast result. But it's running on a dev server right now. So we just created a task for ourselves. Going forward the question is — beyond what I've already shown, there are skills that get loaded separately into Claude Code, there's the need to deploy

**41:56** · the project. And some things we're intentionally skipping today, because I think they deserve a separate video — for example skills. I personally barely use skills in Claude Code, precisely because all my main skills for working through ideas, stack, and so on are loaded into Claude itself. And Claude gives clear briefs to

**42:17** · Claude Code. But a bit about how to deploy all of this — of course I need to tell you. Well, obviously when you're creating a project and making it not just for localhost, even if you do make it for a dev server — connect GitHub to your project regardless. It'll be done as simply as possible here. From the category of: go into that same dialogue and ask "please give me a prompt on how to connect GitHub to my project."

### About Skills and Limitations

### How to Connect GitHub

**42:45** · You'll need GitHub for two things.

**42:47** · First — it's a place where all your development history will be stored, so that if you or the agent make a mistake somewhere, you can go back three commits with GitHub's help. Second, if we're uploading our project to a server, then GitHub is an intermediary link. So there's your dev server where you do development. Then you push it to

### How Deployment Works

**43:11** · GitHub. This is where your project is stored, completely free. And then from GitHub specifically it's sent to the server — the final stage where your domain is connected, your application is deployed and everything works properly.

**43:25** · Here it gave me a prompt — you copy it, paste it exactly into Claude Code, and it gives you a full instruction with connection. The only thing — make sure your project is private so keys don't leak. That's also important. Regarding deployment too — where to do it. You ask it in advance for a prompt on deployment optimization. From the category of: I'm planning to upload this project to a server. Study my code and tell me

### Where to Host Your Project

**43:46** · how I can do this, say, in the case of Russian or foreign servers. About where and how to upload a project if you have a foreign card. And I think that living in Russia without a foreign card right now is absolute madness. So this is the most important thing you'll need in vibe-coding. And a foreign card costs around 10,000 rubles I think somewhere — but it frees you from all the headaches, and then you use Railway.

**44:07** · Railway is basically a hosting where everything will be stored — both the database and your application — and for $20 there you get a huge number of advantages. So Railway is simply the cheapest and most convenient thing for deployment. If you need to do this for a client, use Timeweb.

**44:24** · That's a Russian server, and there you'll simply be complying with Russian law. But we'll talk about all of this in separate lessons. So be sure to subscribe to this channel, follow the links, grab both the system — which will have additional lessons — and the materials from the video, and the prompt enhancer. And we'll see each other in the next videos. The last one is here from the on-screen hint. Bye.
