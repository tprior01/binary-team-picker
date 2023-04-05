# Binary Team Picker

### Overview

A flask application used to pick balanced football teams from a pool of available players. For a pool of size ```n``` there 
are $\\frac{n!}{2(n / 2)!^2}$ team combinations, which can be represented by every binary number of ```n``` digits that has an 
even number of ```0```s and ```1```s. That's 426 combinations for my weekly six-a-side team or 352716 combinations for two 
eleven-a-side teams. Each week the rating of the winners are incremented and the losers decremented. From this the 
scores of every team combination can be compared and only the lowest and therefore fairest team combinations are 
considered.

The table below shows the number of potential line-ups for a given pool size:

<table>
<tr> <td> pool size </td> <td> potential line-ups </td> </tr>
<tr> <td> 2 </td> <td> 1 </td> </tr>
<tr> <td> 4 </td> <td> 3 </td> </tr>
<tr> <td> 6 </td> <td> 10 </td> </tr>
<tr> <td> 8 </td> <td> 35 </td> </tr>
<tr> <td> 10 </td> <td> 126 </td> </tr>
<tr> <td> 12 </td> <td> 426 </td> </tr>
<tr> <td> 14 </td> <td> 1716 </td> </tr>
<tr> <td> 16 </td> <td> 6435 </td> </tr>
<tr> <td> 18 </td> <td> 24310 </td> </tr>
<tr> <td> 20 </td> <td> 92378 </td> </tr>
<tr> <td> 22 </td> <td> 352716 </td> </tr>
</table>


### Example

There are four players in the pool represented by the following json:

```json
{
"player1": {
  "name": "tom",
  "rating": 4.9
},
"player2": {
  "name": "harry",
  "rating": 5.0
},
"player3": {
  "name": "richard",
  "rating": 4.8
},
"player4": {
  "name": "elaine",
  "rating": 5.1
}
}
```

The binary numbers ```1001```, ```1010``` and ```1100``` represent all possible line-ups. The scores of each team member are 
summed to get a team rating. The difference between the ratings of each team are compared and only the line-ups with the 
lowest difference are considered. 

```json
{
  "possible line-ups": {
    "1001": {"team0": {"harry", "richard"}, "team1": {"tom", "elaine"}},
    "1010": {"team0": {"harry", "elaine"}, "team1": {"tom", "richard"}}, 
    "1100": {"team0": {"richard", "elaine"}, "team1": {"tom", "harry"}},
  },
  "team ratings": {
    "1001": {"team0": {9.8}, "team1": {10}},
    "1010": {"team0": {10.1}, "team1": {9.7}}, 
    "1100": {"team0": {9.9}, "team1": {9.9}},
  },
  "difference in team ratings": {
    "1001": 0.2,
    "1010": 0.4, 
    "1100": 0.0,
  }
}
```

Therefore the only line-up considered is that represented by ```1100``` 




