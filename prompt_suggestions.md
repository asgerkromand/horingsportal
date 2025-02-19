# Prompt engineering

## Classifying sender

### Focus on classification

- "I have attached 5 jpegs, and they represent pages continuously extracted from a pdf with responses made to a (political) hearing. The task is a binary classification task with labels 0 and 1: For each page, respond 0 if the sender is the same as for the previous page. Respond with 1 if the sender is a new one compared to the previous page. I would like you to output a list with a classification for each continous page-pair, i.e. a list of length 4. Do not include any other information."
  - "I have attached 5 JPEGs, which are consecutive pages extracted from a PDF containing responses to a political hearing. For each pair of consecutive pages, classify whether the sender is the same (0) or different (1) compared to the previous page. Pay close attention to the continuity of the sender across pages, especially when the content spans multiple pages. Output a list of length 4 with the classifications for each consecutive page pair. Do not include any other information."
    - Specifying to pay close attention to continuity when content spans multiple pages.

### Focus on NER

1) "I have attached 5 JPEGs, which are consecutive pages extracted from a PDF containing responses to a Danish political hearing. Each page should be labelled with a sender. Pay close attention to the continuity of the sender across pages, especially when the content spans multiple pages. Also mind the fact that the sender should be an organizational named entity. I would like you to output a list of the label for each page. Make sure that the list is based on the reasonings, you are doing. Do not include any other information."
  - These were the five first pages of a pdf of length 52. I will now attach the five next pages. For the first page (page 6) you should make sure to base your reasoning by comparing to the last page of the prior bundle (page 5).
    - This was the following prompt I made. It would be relevant in case I can only attach 5 jpegs in the api version as well.

2) "I have attached 5 photos, which are consecutive pages extracted from a PDF containing responses to a Danish          political hearing. Each page should be labelled with a sender. Pay close attention to: 

- The continuity of the sender across pages, especially when the content spans multiple pages. 
- The fact that the sender should be an organizational-named entity. 
- The sender can in some cases consists of multiple senders. In such a case, the senders would normally be listed next to each other.
- For some pages it is a scan or a paste of an email-thread. Pay attention to the mail signature here.

Make sure that the list is based on the reasonings, you are doing, and that it has the length 5. Do not include any other information."

1) "I have attached 5 photos, which are consecutive pages extracted from a PDF containing responses to a Danish political hearing. Each page should be labelled with a sender. Pay close attention to: 

- The continuity of the sender across pages, especially when the content spans multiple pages. 
- The fact that the sender should be an organizational-named entity. 
- The sender can in some cases consists of multiple senders. In such a case, the senders would normally be listed next to each other.
- For some pages it is a scan or a paste of an email-thread. Pay attention to the mail signature here.
- Letterheads, signatures, and consistent formatting to confirm the sender on each page. Identify the sender based on the most prominent and consistent information available, such as the letterhead or signature.

For example, if page 1 has a letterhead from SALA, assume page 2 is also from SALA unless there is a clear indication otherwise. After labeling each page, double-check to ensure the sender is consistent with the previous page unless there is a clear change. Also make sure that the list is based on the reasonings, you are doing, and that it has the length 5. Do not include any other information."