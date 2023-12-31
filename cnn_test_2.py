# -*- coding: utf-8 -*-
"""cnn_test_2.ipynb

Automatically generated by Colaboratory.

# Examining a method of text classification via neural nets
"""

from google.colab import drive
drive.mount('/content/drive')

def print_separator():
  print("\n\n***************************************************************************************************************\n\n")

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from keras.wrappers.scikit_learn import KerasClassifier
from sklearn.model_selection import RandomizedSearchCV, GridSearchCV
from keras.models import Sequential
from keras import layers
from keras.backend import clear_session
from keras.preprocessing.text import Tokenizer
from sklearn.feature_extraction.text import CountVectorizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.metrics import accuracy_score
from sklearn.tree import DecisionTreeClassifier
!pip install keras-tcn
from tcn import TCN, tcn_full_summary
from tensorflow.keras.layers import Input, Embedding, Dense, Dropout, SpatialDropout1D
from tensorflow.keras.layers import concatenate, GlobalAveragePooling1D, GlobalMaxPooling1D
from tensorflow.keras.models import Model
import matplotlib.pyplot as plt
plt.style.use('ggplot')
random_state=999

"""# Preprocessing

We use an IMDB movie reviews dataset [1]. It contains 50K movie reviews labelled with a binary sentiment.
"""

source_df = pd.read_csv('/content/drive/My Drive/project_nn_data/IMDB Dataset.csv', sep=',')
source_df['sentiment'] = source_df['sentiment'].replace("positive",1).replace("negative",0)
source_df['review'] = source_df['review'].str.replace('<br />',' ')
print(source_df.head(10))
#Tokenizer handles punctuations removal
print_separator()
print(source_df.info())

def show_review_length_data(reviews):
  temp_list=[]
  result = 0
  for i, seq in enumerate(reviews):
    current_length = len(seq.split())
    temp_list.append(current_length)
    result = max(current_length, result)
  plt.figure(figsize=(12, 5))
  plt.subplot(1, 2, 1)
  x = range(1, len(temp_list) + 1)
  plt.plot(x, temp_list, 'b', label='Number of words')
  plt.title('Review length')
  plt.legend()
  return result
show_review_length_data(source_df['review'])

#keeping max length as 1000
source_df = source_df.loc[source_df['review'].str.split().str.len() <= 1000]
show_review_length_data(source_df['review'])

"""# Creating and testing a baseline model

For a baseline, we train a decision tree classifier over vectorized input
"""

base_reviews_train, base_reviews_test, base_sentiments_train, base_sentiments_test = train_test_split(source_df['review'].values, source_df['sentiment'].values, test_size=0.25, random_state=random_state)

vectorizer = CountVectorizer()
vectorizer.fit(base_reviews_train)

base_reviews_train_vectorized = vectorizer.transform(base_reviews_train)
base_reviews_test_vectorized = vectorizer.transform(base_reviews_test)

model = DecisionTreeClassifier()
model.fit(base_reviews_train_vectorized, base_sentiments_train)
print("Accuracy: {}".format(accuracy_score(base_sentiments_test, model.predict(base_reviews_test_vectorized))))

"""# Defining and training the network

First we obtain the token sequences that will serve as input to our model
"""

# Main settings
epochs = 20
embedding_dim = 100
maxlen = 1000
batch_size=50

reviews = source_df['review'].values
sentiments = source_df['sentiment'].values

# Create training and testing datasets
reviews_train, reviews_test, sentiments_train, sentiments_test = train_test_split(
    reviews, sentiments, test_size=0.25, random_state=random_state)

# Tokenize the datasets using a vocab size of 5000
tokenizer = Tokenizer(num_words=5000)
tokenizer.fit_on_texts(reviews_train)
reviews_train_tokenized_to_sequences = tokenizer.texts_to_sequences(reviews_train)
reviews_test_tokenized_to_sequences = tokenizer.texts_to_sequences(reviews_test)

# Add 1 because of reserved 0 index
vocab_size = len(tokenizer.word_index) + 1

# Pad sequences with zeros until they reach a length equal to maxlen
reviews_train_tokenized_to_sequences = pad_sequences(reviews_train_tokenized_to_sequences, padding='post', maxlen=maxlen)
reviews_test_tokenized_to_sequences = pad_sequences(reviews_test_tokenized_to_sequences, padding='post', maxlen=maxlen)

"""To achieve greater accuracy, we will use pretrained word embeddings in the input layer of the model. Specifically, we use the 100 vector size version of GloVe [2]."""

def create_embedding_matrix(filepath, word_index, embedding_dim):
    embedding_matrix = np.zeros((len(word_index) + 1, embedding_dim))

    with open(filepath) as f:
        for line in f:
            word, *vector = line.split()
            if word in word_index:
                idx = word_index[word]
                embedding_matrix[idx] = np.array(
                    vector, dtype=np.float32)[:embedding_dim]
    return embedding_matrix

embedding_matrix = create_embedding_matrix(
     '/content/drive/My Drive/project_final_year/glove/glove.6B.100d.txt',
     tokenizer.word_index, embedding_dim)

"""A study done by Diardano Raihan [3] compared the state of different deep learning approaches to sentiment analysis. We use the temporal convolutional network model proposed by them due to its high performance compared to other single-model approaches."""

def define_model(kernel_size = 3, activation='relu', input_dim = None,
                   output_dim=300, max_length = None, emb_matrix = None):

    inp = Input( shape=(max_length,))
    x = Embedding(input_dim=input_dim,
                  output_dim=output_dim,
                  input_length=max_length,
                  # Assign the embedding weight with word2vec embedding marix
                  weights = [emb_matrix],
                  # Set the weight to be not trainable (static)
                  trainable = False)(inp)

    x = SpatialDropout1D(0.1)(x)

    x = TCN(128,dilations = [1, 2, 4], return_sequences=True, activation = activation, name = 'tcn1')(x)
    x = TCN(64,dilations = [1, 2, 4], return_sequences=True, activation = activation, name = 'tcn2')(x)

    avg_pool = GlobalAveragePooling1D()(x)
    max_pool = GlobalMaxPooling1D()(x)

    conc = concatenate([avg_pool, max_pool])
    conc = Dense(16, activation="relu")(conc)
    conc = Dropout(0.1)(conc)
    outp = Dense(1, activation="sigmoid")(conc)

    model = Model(inputs=inp, outputs=outp)
    model.compile( loss = 'binary_crossentropy', optimizer = 'adam', metrics = ['accuracy'])

    return model

"""For training and testing, we use grid search over a set of kernel sizes."""

param_grid = dict(kernel_size=[4, 5, 6],
                  activation=['relu'],
                  input_dim=[vocab_size],
                  output_dim=[100],
                  max_length=[maxlen],
                  emb_matrix=[embedding_matrix]
                  )
model = KerasClassifier(build_fn=define_model,
                        epochs=epochs, batch_size=batch_size,
                        verbose=True)
grid = GridSearchCV(estimator=model, param_grid=param_grid,
                          cv=5, verbose=4)
grid_result = grid.fit(reviews_train_tokenized_to_sequences, sentiments_train)

# Evaluate testing set
test_accuracy = grid.score(reviews_test_tokenized_to_sequences, sentiments_test)

grid_result.best_params_,

# Save and evaluate results
s = ('Running {} data set\nBest Accuracy : '
      '{:.4f}\n{}\nTest Accuracy : {:.4f}\n\n')
output_string = s.format(
    'imdb',
    grid_result.best_score_,
    grid_result.best_params_,
    test_accuracy)
print(output_string)

"""Best Accuracy : 0.7534
{'activation': 'relu', 'emb_matrix': array([[ 0.        ,  0.        ,  0.        , ...,  0.        ,
         0.        ,  0.        ],
       [-0.038194  , -0.24487001,  0.72812003, ..., -0.1459    ,
         0.82779998,  0.27061999],
       [-0.071953  ,  0.23127   ,  0.023731  , ..., -0.71894997,
         0.86894   ,  0.19539   ],
       ...,
       [ 0.        ,  0.        ,  0.        , ...,  0.        ,
         0.        ,  0.        ],
       [ 0.44139001,  0.045824  , -0.19343001, ..., -0.48543   ,
         0.13839   ,  0.10041   ],
       [-0.0784    ,  0.45993999, -0.1804    , ..., -0.057571  ,
         0.34176001,  0.37617001]]), 'input_dim': 108575, 'kernel_size': 6, 'max_length': 100, 'output_dim': 100}
Test Accuracy : 0.8476

# References

[1] - https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews

[2] - https://nlp.stanford.edu/projects/glove/

[3] - https://towardsdatascience.com/deep-learning-techniques-for-text-classification-78d9dc40bf7c
"""
