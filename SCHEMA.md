# **Database Schema — How the Data Is Organized**

The app uses SQLite: a database stored in one local file, with no separate database service to install. Each table works like a spreadsheet with a specific purpose.

## **What is stored**

| Table | Purpose |
| --- | --- |
| `users` | Member profiles and background information. |
| `circles` | Circle details, meeting format, capacity, and activity totals. |
| `memberships` | Who belongs to each Circle and who leads it. |
| `topics` | Shared interests, such as leadership or public speaking. |
| `circle_topics` | Topics covered by each Circle. |
| `user_interests` | Topics selected by each member. |
| `activity_logs` | Posts and their reactions, comments, and saves. |
| `circle_tags` | Extra labels from the supplied Circle data. |
| `dataset_metadata` | The reference date for the sample data. |

## How records connect

Members, Circles, and topics have IDs. The linking tables use these IDs instead of copying whole profiles. One member can join several Circles, and each Circle can cover several topics.

Database rules prevent duplicate memberships, links to missing records, and negative counts. A missing capacity limit means the Circle is uncapped—not full.

## **How lookups are faster**

Indexes act like a book’s index. They help find:

- Public Circles with recent activity.
- Circles a member already belongs to, and each Circle’s leaders.
- Members and Circles linked to a topic.
- Posts from a particular Circle and time period.

Some indexes support future improvements; the current app still reads member lists together when ranking.

## **Why this approach**

Separate tables keep information organized and reduce duplication. Stored member counts and activity totals simplify recommendations. These supplied totals are used because the sample member lists and posts may be incomplete. A live system would update and check those totals regularly.
