import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RecentActivity } from './RecentActivity';
import { timestamp } from './overviewEvidence';

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-27T12:00:00Z')); });
afterEach(() => vi.useRealTimers());

const event = (id: string, completed_at: unknown) => ({id, action_label: id, status: 'failed', completed_at, provider_name: 'Recorded provider'});

describe('recorded activity completion times', () => {
    it.each(['2026-02-30T12:00:00Z', '2026-10-27T12:00:00', '2026-10-27T24:00:00Z', '2026-10-27T12:00Z', '2099-01-01T00:00:00Z'])('keeps invalid or future time %s unknown without hiding the action', completed_at => {
        render(<MemoryRouter><RecentActivity evidence={{data: {items: [event('inspect/me', completed_at)]}}} /></MemoryRouter>);
        expect(screen.getByText('Completion time unknown.')).toBeVisible();
        expect(document.querySelector('time')).toBeNull();
        expect(screen.getByRole('link', {name: 'Inspect action →'})).toHaveAttribute('href', '/operations/actions/inspect%2Fme');
        expect(screen.getByText('Some activity records are malformed or incomplete.')).toBeVisible();
        expect(screen.getByText('Failed · inspect/me')).toBeVisible();
        expect(timestamp(completed_at)).toBeNull();
    });
    it.each(['2024-02-29T12:00:00.123456Z', '2026-10-27T14:00:00+02:00', '2026-10-27T07:00:00-05:00'])('retains valid source instant %s', completed_at => {
        render(<MemoryRouter><RecentActivity evidence={{data: {items: [event('known', completed_at)]}}} /></MemoryRouter>);
        const time = document.querySelector('time');
        expect(time).toHaveAttribute('dateTime', new Date(completed_at).toISOString());
        expect(time).toHaveTextContent(new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(completed_at)));
        expect(time).not.toHaveTextContent(new Date(completed_at).toISOString());
        expect(screen.queryByText('Completion time unknown.')).not.toBeInTheDocument();
    });
    it.each(['1969-12-31T12:00:00Z', '1970-01-01T00:00:00Z', '2026-10-27T11:59:00Z'])('sorts known time %s before unverified future records', known => {
        render(<MemoryRouter><RecentActivity evidence={{data: {items: [event('future', '2099-01-01T00:00:00Z'), event('older', '1960-01-01T12:00:00Z'), event('newer', known)]}}} /></MemoryRouter>);
        const items = screen.getAllByRole('listitem');
        expect(within(items[0]).getByText('Failed · newer')).toBeVisible();
        expect(within(items[1]).getByText('Failed · older')).toBeVisible();
        expect(within(items[2]).getByText('Failed · future')).toBeVisible();
        expect(within(items[2]).getByText('Completion time unknown.')).toBeVisible();
    });
});

it('validates newly arrived completion times against the current clock between display ticks', () => {
    const {rerender} = render(<MemoryRouter><RecentActivity evidence={{data: {items: []}}} /></MemoryRouter>);
    vi.setSystemTime(new Date('2026-10-27T12:00:10Z'));
    rerender(<MemoryRouter><RecentActivity evidence={{data: {items: [event('just-arrived', '2026-10-27T12:00:09Z')]}}} /></MemoryRouter>);
    expect(document.querySelector('time')).toHaveAttribute('dateTime', '2026-10-27T12:00:09.000Z');
    expect(screen.queryByText('Completion time unknown.')).not.toBeInTheDocument();
});
