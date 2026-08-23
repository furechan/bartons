use std::iter::Chain;
use std::slice::Iter;

/// Fixed-capacity ring buffer with allocation-free reset and reuse.
pub(crate) struct RingBuffer<T> {
    values: Vec<T>,
    index: usize,
    count: usize,
}

impl<T: Clone + Default> RingBuffer<T> {
    pub(crate) fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "ring-buffer capacity must be > 0");
        Self {
            values: vec![T::default(); capacity],
            index: 0,
            count: 0,
        }
    }
}

impl<T> RingBuffer<T> {
    /// Insert a value, returning the oldest value only when it is evicted.
    pub(crate) fn push(&mut self, value: T) -> Option<T> {
        let evicted = if self.is_full() {
            Some(std::mem::replace(&mut self.values[self.index], value))
        } else {
            self.values[self.index] = value;
            self.count += 1;
            None
        };

        self.index += 1;
        if self.index == self.capacity() {
            self.index = 0;
        }
        evicted
    }

    /// Forget all values without reallocating or overwriting storage.
    pub(crate) fn clear(&mut self) {
        self.index = 0;
        self.count = 0;
    }

    pub(crate) fn count(&self) -> usize {
        self.count
    }

    pub(crate) fn capacity(&self) -> usize {
        self.values.len()
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.count == 0
    }

    pub(crate) fn is_full(&self) -> bool {
        self.count == self.capacity()
    }

    pub(crate) fn oldest(&self) -> Option<&T> {
        self.get(0)
    }

    pub(crate) fn newest(&self) -> Option<&T> {
        self.count.checked_sub(1).and_then(|offset| self.get(offset))
    }

    /// Get a value by chronological index, where zero is the oldest.
    pub(crate) fn get(&self, index: usize) -> Option<&T> {
        if index >= self.count {
            return None;
        }
        let start = if self.is_full() { self.index } else { 0 };
        Some(&self.values[(start + index) % self.capacity()])
    }

    /// Iterate in chronological order, oldest to newest.
    pub(crate) fn iter(&self) -> Chain<Iter<'_, T>, Iter<'_, T>> {
        let (first, second) = if self.is_full() {
            self.values.split_at(self.index)
        } else {
            self.values[..self.count].split_at(self.count)
        };
        second.iter().chain(first.iter())
    }
}

#[cfg(test)]
mod tests {
    use super::RingBuffer;

    #[test]
    fn warms_up_evicts_and_wraps_in_order() {
        let mut buffer = RingBuffer::<i32>::new(3);
        assert_eq!(buffer.push(1), None);
        assert_eq!(buffer.push(2), None);
        assert_eq!(buffer.count(), 2);
        assert_eq!(buffer.capacity(), 3);
        assert_eq!(buffer.iter().copied().collect::<Vec<_>>(), [1, 2]);
        assert_eq!(buffer.push(3), None);
        assert!(buffer.is_full());
        assert_eq!(buffer.push(4), Some(1));
        assert_eq!(buffer.oldest(), Some(&2));
        assert_eq!(buffer.newest(), Some(&4));
        assert_eq!(buffer.get(1), Some(&3));
        assert_eq!(buffer.iter().copied().collect::<Vec<_>>(), [2, 3, 4]);
    }

    #[test]
    fn clear_restarts_warmup_without_reallocation() {
        let mut buffer = RingBuffer::<i32>::new(2);
        buffer.push(1);
        buffer.push(2);
        buffer.clear();
        assert!(buffer.is_empty());
        assert_eq!(buffer.count(), 0);
        assert_eq!(buffer.push(3), None);
        assert_eq!(buffer.iter().copied().collect::<Vec<_>>(), [3]);
    }
}
