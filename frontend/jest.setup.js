import '@testing-library/jest-dom'

// Mock scrollIntoView which is not implemented in JSDOM
Element.prototype.scrollIntoView = jest.fn()
