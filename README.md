# TournamentPreview
Generate list of notable players for each game

example usage: ```python TournamentPreview.py https://start.gg/tournament/texas-showdown-2023 example_discriminators.txt --seeds 16

Can be used to get an entire tournament or just a single game, accepted formats include:
-Whole start.gg links, e.g., https://www.start.gg/tournament/evo-japan-2023-1/details
-Just tournament slugs, e.g., tournament/texas-showdown2023
-shorthand tournament slugs, e.g., evo
-links to events, e.g., https://www.start.gg/tournament/frosty-faustings-xv-2023/event/the-king-of-fighters-xv-ps4-pro-2
-event slugs, e.g., tournament/evo-2022/event/guilty-gear-strive-1

discriminator list is a list of start.gg discriminators for players to include in all lists, regardless of their seeding
