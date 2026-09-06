# Five-minute team demonstration

All timings, jobs, sectors and safety-related assumptions in this demo are fictional.

## 1. Establish the workflow

Open the local website. Show the three demo profile buttons: two maintenance-team requesters and one officer. Explain that these are deliberately simulated identities; actual Supabase Auth is optional and separately configured.

Sign in as **Planning officer**. Show the two pending requests and two locked bookings.

## 2. Explain one hidden conflict

R01 works in S02 while R03 wants S01. The work sectors differ, but the jobs have opposite requirements for their shared power zone Z01. The conflict panel also shows R04's engineer/equipment conflict and pooled manpower shortage.

Do not say that these are verified operator rules. They are synthetic model rules designed to show a mechanism.

## 3. Calculate a plan

Click **Generate proposal**. Point to the engine label: the default is tiny-demo search, not CP-SAT. When CP-SAT has been installed and enabled, its name will be shown instead.

Show R03 at 02:30 and R04 at 02:35. Switch timeline views. R04's S03 protection row is not a duplicate job. The proposal has not yet booked anything.

## 4. Change something live

Before publishing, open **Resources & activity** and mark E01 unavailable after 02:20. Return to planning. The old proposal is stale and cannot be committed.

Generate a fresh proposal. R04 can use qualified E04 while respecting Q01's transfer allowance. The answer changed because an input changed, not because the frontend moved a fixed animation.

## 5. Approve and view as requester

Approve and publish the updated proposal. Sign out and choose **Track team**. The requester sees its own allocations. Other work is anonymous occupancy. Submit a new request and refresh to show persistence.

No real engineering access has been granted. This demo is planning support only.

## Recovery before presenting again

The demo officer can use **Reset synthetic demo**. That deletes local edits/proposals and reloads the fixture. Do not use reset as a production workflow. It is disabled in Supabase mode.
