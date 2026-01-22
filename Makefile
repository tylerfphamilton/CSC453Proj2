CC = gcc
CFLAGS = -std=c99 -Wall -Wextra -D_XOPEN_SOURCE=700
TARGET  = scheduler 
SRC = scheduler_skeleton.c


all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)
