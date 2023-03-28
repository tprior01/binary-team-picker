# Binary Team Picker

### Overview

This API is used to pick two balanced football teams from a pool of available players.
- Each player is assigned a rating 
- The rating is incremented up for a win and down for a loss
- Every possible line-up of players is represented by the binary numbers which have ```n``` digits and ```n / 2``` 
zeros and ones, where ```n``` is the number of players in the pool and ```n % 2 = 0```
- The binary number is an index representing the two teams (```0```s representing one team, ```1```s representing the 
other)
- We can then calculate the strength of every lineup and judge which is the most balanced


The number of potential line-ups is given by ```(n! / 2) / (n / 2)! ** 2 ```. The number of potential line-ups for a given 
pool size is listed below:

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




