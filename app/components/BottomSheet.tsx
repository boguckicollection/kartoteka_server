import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Button,
  Modal,
  Animated,
  TouchableWithoutFeedback,
  Dimensions
} from 'react-native';
import { PanGestureHandler, State } from 'react-native-gesture-handler';
import { colors } from '../styles/commonStyles';

interface SimpleBottomSheetProps {
  children?: React.ReactNode;
  isVisible?: boolean;
  onClose?: () => void;
}

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

// Snap positions for the bottom sheet
const SNAP_POINTS = {
  HALF: SCREEN_HEIGHT * 0.5,
  FULL: SCREEN_HEIGHT * 0.8,
  CLOSED: SCREEN_HEIGHT,
};

const SimpleBottomSheet: React.FC<SimpleBottomSheetProps> = ({
  children,
  isVisible = false,
  onClose
}) => {
  const translateY = useRef(new Animated.Value(SCREEN_HEIGHT)).current;
  const gestureTranslateY = useRef(new Animated.Value(0)).current;
  const backdropOpacity = useRef(new Animated.Value(0)).current;
  const [currentSnapPoint, setCurrentSnapPoint] = useState(SNAP_POINTS.HALF);
  const lastGestureY = useRef(0);
  const startPositionY = useRef(0);

  useEffect(() => {
    if (isVisible) {
      setCurrentSnapPoint(SNAP_POINTS.HALF);
      gestureTranslateY.setValue(0);
      Animated.parallel([
        Animated.timing(translateY, {
          toValue: SCREEN_HEIGHT - SNAP_POINTS.HALF,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 0.5,
          duration: 300,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      setCurrentSnapPoint(SNAP_POINTS.CLOSED);
      gestureTranslateY.setValue(0);
      Animated.parallel([
        Animated.timing(translateY, {
          toValue: SCREEN_HEIGHT,
          duration: 250,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [isVisible, translateY, backdropOpacity]);

  const handleBackdropPress = () => {
    onClose?.();
  };

  const snapToPoint = (point: number) => {
    setCurrentSnapPoint(point);
    gestureTranslateY.setValue(0);
    Animated.timing(translateY, {
      toValue: SCREEN_HEIGHT - point,
      duration: 300,
      useNativeDriver: true,
    }).start();
  };

  // Determines the closest snap point based on velocity and position
  const getClosestSnapPoint = (currentY: number, velocityY: number) => {
    const currentPosition = SCREEN_HEIGHT - currentY;

    if (velocityY > 1000) return SNAP_POINTS.CLOSED;
    if (velocityY < -1000) return SNAP_POINTS.FULL;

    const distances = [
      { point: SNAP_POINTS.HALF, distance: Math.abs(currentPosition - SNAP_POINTS.HALF) },
      { point: SNAP_POINTS.FULL, distance: Math.abs(currentPosition - SNAP_POINTS.FULL) },
    ];

    if (currentPosition < SNAP_POINTS.HALF * 0.5) {
      return SNAP_POINTS.CLOSED;
    }

    distances.sort((a, b) => a.distance - b.distance);
    return distances[0].point;
  };

  // Handles pan gesture events with boundary clamping
  const onGestureEvent = (event: any) => {
    const { translationY } = event.nativeEvent;
    lastGestureY.current = translationY;

    const currentBasePosition = SCREEN_HEIGHT - currentSnapPoint;
    const intendedPosition = currentBasePosition + translationY;

    const minPosition = SCREEN_HEIGHT - SNAP_POINTS.FULL;
    const maxPosition = SCREEN_HEIGHT;

    const clampedPosition = Math.max(minPosition, Math.min(maxPosition, intendedPosition));
    const clampedTranslation = clampedPosition - currentBasePosition;

    gestureTranslateY.setValue(clampedTranslation);
  };

  // Handles gesture state changes (begin/end) for snapping behavior
  const onHandlerStateChange = (event: any) => {
    const { state, translationY, velocityY } = event.nativeEvent;

    if (state === State.BEGAN) {
      startPositionY.current = SCREEN_HEIGHT - currentSnapPoint;
    } else if (state === State.END) {
      const currentBasePosition = SCREEN_HEIGHT - currentSnapPoint;
      const intendedPosition = currentBasePosition + translationY;

      const minPosition = SCREEN_HEIGHT - SNAP_POINTS.FULL;
      const maxPosition = SCREEN_HEIGHT;

      const finalY = Math.max(minPosition, Math.min(maxPosition, intendedPosition));
      const targetSnapPoint = getClosestSnapPoint(finalY, velocityY);

      gestureTranslateY.setValue(0);

      if (targetSnapPoint === SNAP_POINTS.CLOSED) {
        onClose?.();
      } else {
        snapToPoint(targetSnapPoint);
      }
    }
  };

  return (
    <Modal
      visible={isVisible}
      transparent
      animationType="none"
      statusBarTranslucent
    >
      <View style={styles.container}>
        <TouchableWithoutFeedback onPress={handleBackdropPress}>
          <Animated.View
            style={[
              styles.backdrop,
              { opacity: backdropOpacity }
            ]}
          />
        </TouchableWithoutFeedback>

        <PanGestureHandler
          onGestureEvent={onGestureEvent}
          onHandlerStateChange={onHandlerStateChange}
        >
          <Animated.View
            style={[
              styles.bottomSheet,
              {
                transform: [
                  { translateY: Animated.add(translateY, gestureTranslateY) }
                ],
              },
            ]}
          >
            <View style={styles.handle} />

            <View style={styles.contentContainer}>
              {children || (
                <View style={styles.defaultContent}>
                  <Text style={styles.title}>Bottom Sheet 🎉</Text>
                  <Text style={styles.description}>
                    This is a custom bottom sheet implementation.
                    Try dragging it up and down!
                  </Text>
                  <Button
                    title="Close"
                    onPress={onClose}
                  />
                </View>
              )}
            </View>
          </Animated.View>
        </PanGestureHandler>
      </View>
    </Modal>
  );
};

SimpleBottomSheet.displayName = 'SimpleBottomSheet';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'black',
  },
  bottomSheet: {
    height: SNAP_POINTS.FULL,
    backgroundColor: colors.background || '#ffffff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: -3,
    },
    shadowOpacity: 0.27,
    shadowRadius: 4.65,
    elevation: 6,
  },
  handle: {
    width: 40,
    height: 4,
    backgroundColor: colors.grey || '#cccccc',
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 8,
    marginBottom: 8,
  },
  contentContainer: {
    flex: 1,
    padding: 16,
  },
  defaultContent: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: 16,
  },
  description: {
    fontSize: 16,
    color: colors.text,
    textAlign: 'center',
    marginBottom: 20,
  },
});

export default SimpleBottomSheet;
